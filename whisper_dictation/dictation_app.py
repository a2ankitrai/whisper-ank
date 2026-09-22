"""Main dictation application with push-to-talk and text processing pipeline."""

from __future__ import annotations

import faulthandler
import os
import queue
import signal
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from .audio_feedback import AudioFeedback
from .audio_recorder import AudioRecorder
from .config import DictationConfig
from .grammar_corrector import create_grammar_corrector
from .keyboard import _resilient_listener_class, key_to_char, live_modifiers
from .text_processors import FillerRemover, SnippetExpander, TextProcessor
from .text_typer import TextTyper
from .transcriber import Transcriber
from .translator import ArgosTranslator, Translator


class DictationApp:
    """Main dictation application with push-to-talk and text processing pipeline."""

    def __init__(
        self,
        model_size: str = "base",
        language: str | None = "en",
        enable_grammar: bool = False,
        config: DictationConfig | None = None,
    ):
        # Use config if provided, otherwise build from legacy parameters
        if config is None:
            config = DictationConfig(
                model_size=model_size,
                language=language,
                grammar_engine="languagetool" if enable_grammar else None,
            )

        self.config = config

        # Core components
        self.recorder = AudioRecorder()
        self.typer = TextTyper()
        self.audio_feedback = AudioFeedback(enabled=config.audio_feedback)
        self._build_pipeline(config)

        # Legacy compatibility
        self.enable_grammar = config.grammar_engine is not None

        # State
        self.is_recording = False
        self.running = True
        self.pressed_modifiers: set[str] = set()
        self.hotkey = config.hotkey
        self.recording_mode = config.recording_mode
        self.replay_hotkey = config.replay_hotkey
        self.history: deque[str] = deque(maxlen=10)
        self.lock = threading.Lock()

        # Tracks whether the CGEventTap is actually *delivering* key events,
        # not just whether it was created. A tap can be created successfully
        # (no exception, `CGEventTapIsEnabled` reports True) while still
        # receiving zero events, e.g. when the running binary lost Input
        # Monitoring trust (common after a Homebrew Python upgrade replaces
        # the interpreter binary) but Accessibility trust still looks
        # granted. Without this, that failure mode is completely silent.
        self.last_event_at: float | None = None
        self._no_events_warned_at: float | None = None

        # Recording start/stop is executed on a dedicated worker thread so the
        # keyboard callbacks stay non-blocking (see _worker_loop).
        self.commands: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.processing_threads: list[threading.Thread] = []
        self.command_started_at: tuple[float, str] | None = None

    def _build_pipeline(self, config: DictationConfig) -> None:
        """(Re)build the transcriber and text-processing pipeline from config.

        Builds everything into local variables first and only assigns to
        `self` once all construction succeeds, so a failure (e.g. an
        invalid model size) never leaves the app with a half-updated
        pipeline — see apply_config().
        """
        transcriber = Transcriber(
            model_size=config.model_size,
            language=config.language,
            translate=config.translate_to_english,
            multilingual=config.multilingual,
            hotwords=config.hotwords,
        )

        processors: list[TextProcessor] = []

        # 1. Filler removal (first, to clean up raw transcription)
        if config.remove_fillers:
            processors.append(FillerRemover())

        # 2. Snippet expansion
        if config.snippets:
            processors.append(SnippetExpander(config.snippets))

        # 3. Grammar correction
        grammar_corrector = create_grammar_corrector(
            config.grammar_engine,
            config.language or "en"
        )
        if grammar_corrector:
            processors.append(grammar_corrector)

        # 4. Translation (English → target language)
        translator: Translator | None = None
        if config.target_language:
            translator = ArgosTranslator(
                source_lang="en",
                target_lang=config.target_language
            )
            processors.append(translator)

        self.transcriber = transcriber
        self.processors = processors
        self.grammar_corrector = grammar_corrector
        self.translator = translator

    def apply_config(self, new_config: DictationConfig) -> None:
        """Apply a changed config to the running app without a restart.

        Rebuilds the (possibly slow, possibly failing) pipeline first;
        only if that succeeds do the cheap live attributes and self.config
        get updated, so a bad config never leaves the app half-changed.
        """
        self._build_pipeline(new_config)

        with self.lock:
            self.hotkey = new_config.hotkey
            self.recording_mode = new_config.recording_mode
            self.replay_hotkey = new_config.replay_hotkey
            self.audio_feedback.enabled = new_config.audio_feedback

        self.config = new_config

    # -- Worker -------------------------------------------------------------

    def _worker_loop(self):
        """Serially execute recording commands off the keyboard callback thread.

        macOS disables a CGEventTap whose callback is slow; opening the audio
        stream or playing a sound inside the callback is exactly that kind of
        slow work and used to silently kill the hotkey until a restart.
        """
        while self.running:
            try:
                command = self.commands.get(timeout=0.2)
            except queue.Empty:
                continue

            self.command_started_at = (time.monotonic(), command)
            try:
                if command == "start":
                    self.audio_feedback.play_start()
                    self.recorder.start()
                elif command == "stop":
                    self.audio_feedback.play_stop()
                    # Grab the audio here (bounded), but transcribe on a
                    # separate thread: transcription can take seconds and must
                    # never delay the next recording.
                    audio = self.recorder.stop()
                    self._spawn_processing(audio)
                elif command == "replay":
                    self._replay_last()
            except Exception as e:
                print(f"❌ Recording error: {e}", file=sys.stderr)
                with self.lock:
                    self.is_recording = False
            finally:
                self.command_started_at = None
                self.commands.task_done()

    def _spawn_processing(self, audio):
        """Transcribe and type a finished recording on its own thread."""
        thread = threading.Thread(
            target=self._process_recording, args=(audio,), daemon=True
        )
        with self.lock:
            self.processing_threads = [
                t for t in self.processing_threads if t.is_alive()
            ]
            self.processing_threads.append(thread)
        thread.start()

    def wait_for_processing(self, timeout: float = 10.0):
        """Block until in-flight transcriptions finish (used by tests)."""
        with self.lock:
            threads = list(self.processing_threads)
        for thread in threads:
            thread.join(timeout)

    def _start_recording(self):
        """Flag recording as active and queue the actual work. Caller holds lock."""
        self.is_recording = True
        print("🎤 Recording... (release to transcribe)")
        self.commands.put("start")

    def _stop_recording(self):
        """Flag recording as finished and queue the actual work. Caller holds lock."""
        self.is_recording = False
        self.commands.put("stop")

    def _replay_last(self):
        """Retype the most recent transcription (replay hotkey)."""
        if not self.history:
            print("⚠️  No previous transcription to replay")
            return
        text = self.history[-1]
        print(f"🔁 Replaying: {text}")
        self.typer.type_text(text + " ")

    # -- Keyboard callbacks (must return fast) ------------------------------

    def _on_press(self, key):
        """Handle key press."""
        from pynput.keyboard import Key

        # Recorded for *any* key, not just modifiers: this is how we know the
        # event tap is actually delivering events at all (see last_event_at).
        self.last_event_at = time.monotonic()

        modifier = self._key_to_modifier(key)
        if modifier:
            with self.lock:
                was_full = self.hotkey.issubset(self.pressed_modifiers)
                self.pressed_modifiers.add(modifier)
                now_full = self.hotkey.issubset(self.pressed_modifiers)

                if self.recording_mode == "toggle":
                    # Fire once on the rising edge, not on every repeated
                    # press while the combo stays held down.
                    if now_full and not was_full:
                        if self.is_recording:
                            self._stop_recording()
                        else:
                            self._start_recording()
                elif now_full and not self.is_recording:
                    self._start_recording()
        else:
            # Not a modifier: check it against the replay hotkey's trailing
            # key (e.g. the 'v' in cmd+shift+v).
            replay_modifiers, replay_key = self.replay_hotkey
            char = key_to_char(key)
            if char == replay_key and replay_modifiers.issubset(self.pressed_modifiers):
                self.commands.put("replay")

        # Escape to quit
        if key == Key.esc:
            print("\n👋 Exiting...")
            self.running = False
            return False

    def _on_release(self, key):
        """Handle key release."""
        self.last_event_at = time.monotonic()

        modifier = self._key_to_modifier(key)
        if modifier:
            with self.lock:
                self.pressed_modifiers.discard(modifier)

                # Push-to-talk only: toggle mode starts/stops on press, not
                # on release, so recording can continue with no keys held.
                if (
                    self.recording_mode == "push_to_talk"
                    and self.is_recording
                    and not self.hotkey.issubset(self.pressed_modifiers)
                ):
                    self._stop_recording()

    def _resync_modifiers(self):
        """Reconcile our tracked key state with the real hardware state.

        Key events can be missed (app in background, event tap disabled,
        Cmd-Tab stealing the release). Without this, `is_recording` could stay
        stuck at True and every later hotkey press would be ignored.
        """
        with self.lock:
            if not self.pressed_modifiers and not self.is_recording:
                # Nothing tracked as held: nothing can be stale.
                return

        try:
            actual = live_modifiers()
        except Exception as e:
            print(f"⚠️  Could not read modifier state: {e}", file=sys.stderr)
            return

        with self.lock:
            if actual == self.pressed_modifiers:
                return
            self.pressed_modifiers = actual
            if (
                self.recording_mode == "push_to_talk"
                and self.is_recording
                and not self.hotkey.issubset(actual)
            ):
                print("⚠️  Missed key release detected, finishing recording")
                self._stop_recording()

    def _check_event_flow(self, listener_started_at: float):
        """Warn if the keyboard listener is alive but delivering no events.

        A CGEventTap can be created successfully and report itself as
        "enabled" while still never receiving a single key event, most
        commonly because the running binary lost (or never had) Input
        Monitoring trust in System Settings — a separate grant from
        Accessibility, and one that Homebrew silently invalidates every time
        it replaces the Python.framework binary on upgrade. That failure
        mode previously looked identical to "nothing happens", with zero
        diagnostics. Re-warn periodically (not just once) since a user may
        only glance at the log well after startup.
        """
        now = time.monotonic()
        if self.last_event_at is not None:
            self._no_events_warned_at = None
            return

        since_start = now - listener_started_at
        if since_start < 8:
            return
        if self._no_events_warned_at is not None and now - self._no_events_warned_at < 30:
            return

        self._no_events_warned_at = now
        print(
            f"⚠️  No keyboard events received in {since_start:.0f}s — the hotkey "
            "will not work. This usually means Input Monitoring (not just "
            "Accessibility) permission is missing or stale for:\n"
            f"      {sys.executable}\n"
            "   Fix: System Settings → Privacy & Security → Input Monitoring "
            "(and Accessibility) → remove this entry if present, then re-add "
            "it via the '+' button and restart the app. This commonly happens "
            "again after `brew upgrade python`, which replaces the binary.",
            file=sys.stderr,
        )

    def _key_to_modifier(self, key) -> str | None:
        """Convert pynput key to modifier name."""
        from pynput.keyboard import Key

        mapping = {
            Key.cmd: "cmd",
            Key.cmd_l: "cmd",
            Key.cmd_r: "cmd",
            Key.shift: "shift",
            Key.shift_l: "shift",
            Key.shift_r: "shift",
            Key.ctrl: "ctrl",
            Key.ctrl_l: "ctrl",
            Key.ctrl_r: "ctrl",
            Key.alt: "alt",
            Key.alt_l: "alt",
            Key.alt_r: "alt",
        }
        return mapping.get(key)

    def _process_recording(self, audio=None):
        """Process recorded audio: transcribe and apply processing pipeline."""
        print("⏳ Processing...")

        if audio is None:
            audio = self.recorder.stop()
        if audio is None or len(audio) < 3200:  # < 0.2 seconds
            print("⚠️  Recording too short")
            print("🎯 Ready...")
            return

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            self.recorder.save_wav(audio, temp_path)
            text = self.transcriber.transcribe(temp_path)

            if text:
                print(f"📝 Transcribed: {text}")

                # Apply text processing pipeline
                processed = text
                for processor in self.processors:
                    new_text = processor.process(processed)
                    if new_text != processed:
                        processor_name = type(processor).__name__
                        print(f"✨ {processor_name}: {new_text}")
                        processed = new_text

                self.history.append(processed)
                self.typer.type_text(processed + " ")
            else:
                print("⚠️  No speech detected")

        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
        finally:
            temp_path.unlink(missing_ok=True)

        print("🎯 Ready...")

    def _handle_signal(self, signum, frame):
        """Handle termination signals gracefully instead of dying abruptly.

        SIGHUP is sent when the controlling terminal closes (e.g. a plain
        `command &` job without nohup); ignoring it keeps the app alive in
        the background. SIGTERM (e.g. from launchd/kill) triggers a clean
        shutdown instead of an abrupt kill.
        """
        if signum == signal.SIGHUP:
            return
        print(f"\n👋 Received signal {signum}, shutting down...")
        self.running = False
        # If the main thread is wedged in a blocking OS call, a graceful exit
        # can never happen; force one shortly after.
        threading.Timer(3.0, self._force_exit).start()

    @staticmethod
    def _force_exit():
        """Last-resort exit used when graceful shutdown stalls."""
        print("⚠️  Graceful shutdown stalled, forcing exit", file=sys.stderr)
        sys.stderr.flush()
        os._exit(1)

    def run(self):
        """Run the dictation app."""
        # Dump every thread's stack on SIGUSR1 (`kill -USR1 <pid>`) so a hang
        # can be diagnosed from dictation.log instead of guessed at.
        faulthandler.enable()
        try:
            faulthandler.register(signal.SIGUSR1, all_threads=True, chain=False)
        except Exception:
            pass

        # Ignore SIGHUP so the process survives terminal disconnects when
        # launched in the background, and shut down cleanly on SIGTERM.
        try:
            signal.signal(signal.SIGHUP, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            # Signals can only be registered from the main thread
            pass

        # Build hotkey display strings
        hotkey_display = "+".join(k.capitalize() for k in sorted(self.hotkey))
        replay_modifiers, replay_key = self.replay_hotkey
        replay_display = "+".join(
            k.capitalize() for k in sorted(replay_modifiers)
        ) + f"+{replay_key.upper()}"

        print("\n" + "=" * 60)
        print("🎙️  WHISPER DICTATION")
        print("=" * 60)
        if self.recording_mode == "toggle":
            print(f"Press {hotkey_display} to start recording, press again to stop")
        else:
            print(f"Hold {hotkey_display} to record")
            print("Release to transcribe and type")
        print(f"Press {replay_display} to retype the last transcription")
        print("Press Escape to quit")
        print("-" * 60)

        # Show active features
        features = []
        if self.config.multilingual:
            features.append("Multilingual (code-mixing)")
        else:
            features.append(f"Language: {self.config.language or 'auto'}")

        if self.config.translate_to_english:
            features.append("Translation: → English")

        if self.config.target_language:
            features.append(f"Translation: English → {self.config.target_language}")

        if self.config.grammar_engine:
            features.append(f"Grammar: {self.config.grammar_engine}")

        if self.config.remove_fillers:
            features.append("Filler removal: ON")

        if self.config.hotwords:
            features.append(f"Hotwords: {len(self.config.hotwords)}")

        if self.config.snippets:
            features.append(f"Snippets: {len(self.config.snippets)}")

        if self.config.audio_feedback:
            features.append("Audio feedback: ON")

        for feature in features:
            print(f"  • {feature}")

        print("=" * 60)
        print("\n🎯 Ready...\n")

        listener_cls = _resilient_listener_class()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

        listener = listener_cls(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        listener.start()
        listener_started_at = time.monotonic()
        try:
            listener.wait()
            last_health_check = 0.0
            last_stall_warning = 0.0
            while self.running:
                time.sleep(0.1)

                if not listener.running:
                    # The listener thread died (permissions revoked, tap
                    # creation failed); rebuild it instead of going silent.
                    print("⚠️  Keyboard listener stopped, restarting it...")
                    try:
                        listener.stop()
                    except Exception:
                        pass
                    listener = listener_cls(
                        on_press=self._on_press,
                        on_release=self._on_release,
                    )
                    listener.start()
                    listener_started_at = time.monotonic()
                    self.last_event_at = None
                    self._no_events_warned_at = None
                    listener.wait()
                    self._resync_modifiers()
                    continue

                if listener.ensure_tap_enabled():
                    print("⚠️  Event tap was disabled by macOS, re-enabled it")

                now = time.monotonic()
                if now - last_health_check >= 0.5:
                    last_health_check = now
                    self._resync_modifiers()
                    self._check_event_flow(listener_started_at)

                    started = self.command_started_at
                    if started and now - started[0] > 5:
                        if now - last_stall_warning > 10:
                            last_stall_warning = now
                            print(
                                f"⚠️  Audio command '{started[1]}' has been "
                                f"stuck for {now - started[0]:.0f}s "
                                f"(send SIGUSR1 to this PID for a stack dump)",
                                file=sys.stderr,
                            )
        except Exception as e:
            print(f"\n❌ Listener error: {e}", file=sys.stderr)
            print(
                "   This is often caused by missing Accessibility/Input "
                "Monitoring permission for the Python process.",
                file=sys.stderr,
            )
        finally:
            self.running = False
            try:
                listener.stop()
            except Exception:
                pass
            if self.worker:
                self.worker.join(timeout=2)
            self.recorder.close()
