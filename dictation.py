#!/usr/bin/env python3
"""
Whisper Dictation - Local speech-to-text with typing into any focused application.

Usage:
    python dictation.py [--model MODEL] [--language LANG] [--grammar ENGINE] [--translate]

Controls:
    - Hold Cmd+Shift to record (configurable with --hotkey)
    - Release to transcribe and type into focused app
    - Press Escape to quit

Features:
    - Grammar correction: LanguageTool (rule-based) or Gramformer (AI-based)
    - Translation: Whisper (any→English) or Argos (English→target)
    - Multilingual: Support for code-mixing (e.g., English+Hindi+Dutch)
    - Filler removal: Automatic removal of "um", "uh", "like", etc.
    - Hotwords: Custom dictionary for proper nouns and jargon
    - Audio feedback: Beeps on record start/stop
    - Snippets: Voice-triggered text shortcuts
"""

from __future__ import annotations

import argparse
import faulthandler
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# macOS-specific imports for keyboard simulation and event-tap health checks
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    kCGHIDEventTap,
    CGEventSourceCreate,
    CGEventSourceFlagsState,
    CGEventSetFlags,
    CGEventTapEnable,
    CGEventTapIsEnabled,
    kCGEventSourceStateHIDSystemState,
    kCGEventSourceStateCombinedSessionState,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
)
from Quartz.CoreGraphics import CGEventKeyboardSetUnicodeString

#: Live modifier flag masks, used to re-synchronise our key state with the OS.
MODIFIER_FLAG_MASKS = {
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
}


def live_modifiers() -> set[str]:
    """Return the modifiers that are *physically* held down right now.

    Reading the hardware state lets us recover from press/release events that
    were never delivered (e.g. while the event tap was disabled).
    """
    flags = CGEventSourceFlagsState(kCGEventSourceStateCombinedSessionState)
    return {name for name, mask in MODIFIER_FLAG_MASKS.items() if flags & mask}


_RESILIENT_LISTENER_CLS = None


def _resilient_listener_class():
    """Build (once) a pynput listener that exposes its macOS event tap.

    macOS silently disables an event tap whose callback is too slow
    (`kCGEventTapDisabledByTimeout`) and pynput never re-enables it, so the
    hotkey stops working until the app is restarted. Keeping a handle on the
    tap lets us detect that and switch it back on.
    """
    global _RESILIENT_LISTENER_CLS
    if _RESILIENT_LISTENER_CLS is None:
        from pynput import keyboard

        class ResilientListener(keyboard.Listener):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._event_tap = None

            def _create_event_tap(self):
                self._event_tap = super()._create_event_tap()
                return self._event_tap

            def ensure_tap_enabled(self) -> bool:
                """Re-enable the tap if macOS disabled it. True if it was dead."""
                tap = self._event_tap
                if tap is None:
                    return False
                try:
                    if CGEventTapIsEnabled(tap):
                        return False
                    CGEventTapEnable(tap, True)
                    return True
                except Exception:
                    return False

        _RESILIENT_LISTENER_CLS = ResilientListener
    return _RESILIENT_LISTENER_CLS


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class DictationConfig:
    """Configuration for the dictation application."""

    # Model settings
    model_size: str = "base"
    language: str | None = "en"
    
    # Grammar correction
    grammar_engine: str | None = None  # None, "languagetool", or "gramformer"
    
    # Translation settings
    translate_to_english: bool = False  # Use Whisper's translate task
    target_language: str | None = None  # For Argos translation (e.g., "nl" for Dutch)
    
    # Multilingual / code-mixing
    multilingual: bool = False
    
    # Text processing
    remove_fillers: bool = True
    hotwords: list[str] = field(default_factory=list)
    
    # Snippets (voice shortcuts)
    snippets: dict[str, str] = field(default_factory=dict)
    
    # Audio feedback
    audio_feedback: bool = True
    
    # Hotkey configuration
    hotkey: set[str] = field(default_factory=lambda: {"cmd", "shift"})
    
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "DictationConfig":
        """Create config from command-line arguments."""
        config = cls(
            model_size=args.model,
            language=None if args.multilingual else args.language,
            grammar_engine=args.grammar,
            translate_to_english=args.translate,
            target_language=args.target_language,
            multilingual=args.multilingual,
            remove_fillers=not args.keep_fillers,
            hotwords=args.hotwords.split(",") if args.hotwords else [],
            audio_feedback=not args.no_audio_feedback,
        )
        
        # Parse hotkey
        if args.hotkey:
            config.hotkey = cls._parse_hotkey(args.hotkey)
        
        # Load snippets from file if provided
        if args.snippets_file:
            config.snippets = cls._load_snippets(args.snippets_file)
        
        return config
    
    @staticmethod
    def _parse_hotkey(spec: str) -> set[str]:
        """Parse a "cmd+shift" style hotkey spec into modifier names.

        Unknown modifiers are rejected loudly: silently accepting them would
        produce a hotkey that can never match, so the app would start up
        looking healthy but never record anything.
        """
        hotkey = {part.strip().lower() for part in spec.split("+") if part.strip()}
        if not hotkey:
            raise ValueError("Hotkey must contain at least one modifier")
        unknown = sorted(hotkey - set(MODIFIER_FLAG_MASKS))
        if unknown:
            supported = "+".join(sorted(MODIFIER_FLAG_MASKS))
            raise ValueError(
                f"Unsupported hotkey modifier(s): {', '.join(unknown)}. "
                f"Supported modifiers: {supported}"
            )
        return hotkey

    @staticmethod
    def _load_snippets(path: str) -> dict[str, str]:
        """Load snippets from a file (format: trigger=text per line)."""
        snippets = {}
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        trigger, text = line.split("=", 1)
                        snippets[trigger.strip().lower()] = text.strip()
        except FileNotFoundError:
            print(f"⚠️  Snippets file not found: {path}", file=sys.stderr)
        except (OSError, UnicodeDecodeError) as e:
            print(f"⚠️  Could not read snippets file {path}: {e}", file=sys.stderr)
        return snippets


# =============================================================================
# Audio Recording
# =============================================================================


class AudioRecorder:
    """Records audio from the microphone.

    The input stream is opened once and kept open for the lifetime of the app.
    Opening/closing a CoreAudio stream for every dictation is what used to
    deadlock inside PortAudio (`sounddevice.abort()` never returning), which
    wedged the hotkey and left the microphone dead until a restart. Starting
    and stopping a recording is now just a flag flip, which also means no
    audio is lost while the device spins up.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_chunks: list[np.ndarray] = []
        self.stream = None
        self.lock = threading.Lock()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"⚠️  Audio status: {status}", file=sys.stderr)
        # Grab the buffer *before* re-checking the flag and never take the
        # lock here: this runs on PortAudio's real-time thread. Reading in
        # this order means a callback that races with stop() appends to the
        # list that was just swapped out (and discarded) instead of leaking
        # audio into the next recording.
        chunks = self.audio_chunks
        if self.recording:
            chunks.append(indata.copy())

    def _ensure_stream(self):
        """Open the shared input stream, or replace it if it died."""
        stream = self.stream
        if stream is not None:
            try:
                if stream.active:
                    return
            except Exception:
                pass
            # Dead stream (device unplugged, sample rate changed...): drop it
            # in the background, since closing it may block.
            self.stream = None
            self._close_stream(stream)

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        stream.start()
        self.stream = stream

    def start(self):
        """Start capturing audio into the buffer."""
        with self.lock:
            self.audio_chunks = []
            self.recording = True

        try:
            self._ensure_stream()
        except Exception:
            with self.lock:
                self.recording = False
            raise

    def stop(self) -> np.ndarray | None:
        """Stop capturing and return the recorded audio.

        The stream deliberately stays open; see the class docstring.
        """
        with self.lock:
            self.recording = False
            chunks, self.audio_chunks = self.audio_chunks, []

        if not chunks:
            return None

        audio = np.concatenate(chunks, axis=0).flatten()
        return audio

    def close(self):
        """Release the microphone (called on shutdown)."""
        with self.lock:
            self.recording = False
        stream, self.stream = self.stream, None
        if stream is not None and not self._close_stream(stream):
            print(
                "⚠️  Audio device did not release in time, continuing anyway",
                file=sys.stderr,
            )

    @staticmethod
    def _close_stream(stream, timeout: float = 2.0) -> bool:
        """Abort and close a stream, giving up after `timeout` seconds.

        PortAudio can block forever here, so it never runs on a thread we
        care about.
        """

        def closer():
            try:
                stream.abort()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

        thread = threading.Thread(target=closer, daemon=True)
        thread.start()
        thread.join(timeout)
        return not thread.is_alive()

    def save_wav(self, audio: np.ndarray, path: Path):
        """Save audio to WAV file.

        Samples are clipped before the int16 conversion; without that, a
        loud passage above 1.0 would wrap around and turn into noise that
        Whisper cannot transcribe.
        """
        import wave

        audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())


# =============================================================================
# Transcription
# =============================================================================


class Transcriber:
    """Transcribes audio using Faster-Whisper with support for translation and multilingual."""

    def __init__(
        self,
        model_size: str = "base",
        language: str | None = "en",
        translate: bool = False,
        multilingual: bool = False,
        hotwords: list[str] | None = None,
    ):
        print(f"⏳ Loading Faster-Whisper model '{model_size}'...")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        self.language = language
        self.translate = translate
        self.multilingual = multilingual
        self.hotwords = hotwords or []
        print("✅ Model loaded!")

    def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio file to text."""
        # Build hotwords string if provided
        hotwords_str = " ".join(self.hotwords) if self.hotwords else None
        
        # Determine task
        task = "translate" if self.translate else "transcribe"
        
        # For multilingual mode, don't specify language (let Whisper detect)
        lang = None if self.multilingual else self.language
        
        segments, info = self.model.transcribe(
            str(audio_path),
            language=lang,
            task=task,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            multilingual=self.multilingual,
            hotwords=hotwords_str,
        )

        text = " ".join(segment.text.strip() for segment in segments)
        return text.strip()


# =============================================================================
# Text Processing Pipeline
# =============================================================================


class TextProcessor(ABC):
    """Abstract base class for text processors."""
    
    @abstractmethod
    def process(self, text: str) -> str:
        """Process the text and return the result."""
        pass


class FillerRemover(TextProcessor):
    """Removes filler words from transcribed text."""
    
    # Common filler words and phrases
    FILLERS = [
        r"\b(um+|uh+|er+|ah+|eh+|hm+|hmm+)\b",
        r"\b(you know|i mean|like|basically|actually|literally|right)\b",
        r"\b(sort of|kind of|you see|well)\b",
    ]
    
    def __init__(self):
        # Compile patterns for efficiency (case-insensitive)
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.FILLERS]
    
    def process(self, text: str) -> str:
        """Remove filler words from text."""
        if not text:
            return text
        
        result = text
        for pattern in self.patterns:
            result = pattern.sub("", result)
        
        # Clean up multiple spaces and trim
        result = re.sub(r"\s+", " ", result).strip()
        return result


class SnippetExpander(TextProcessor):
    """Expands voice command snippets to predefined text."""
    
    def __init__(self, snippets: dict[str, str]):
        self.snippets = {k.lower(): v for k, v in snippets.items()}
    
    def process(self, text: str) -> str:
        """Check if text matches a snippet trigger and expand it."""
        if not text:
            return text
        
        # Check for exact match (case-insensitive)
        lower_text = text.lower().strip()
        if lower_text in self.snippets:
            return self.snippets[lower_text]
        
        # Check for "insert X" pattern
        if lower_text.startswith("insert "):
            snippet_name = lower_text[7:].strip()
            if snippet_name in self.snippets:
                return self.snippets[snippet_name]
        
        return text


# =============================================================================
# Grammar Correction
# =============================================================================


class GrammarCorrector(TextProcessor):
    """Abstract base class for grammar correctors."""
    
    @abstractmethod
    def correct(self, text: str) -> str:
        """Apply grammar corrections to text."""
        pass
    
    def process(self, text: str) -> str:
        """TextProcessor interface - delegates to correct()."""
        return self.correct(text)


class LanguageToolCorrector(GrammarCorrector):
    """Corrects grammar using LanguageTool (rule-based, lazy-loaded)."""

    def __init__(self, language: str = "en-US"):
        self.language = language
        self._tool = None

    def _load_tool(self):
        """Lazy-load LanguageTool on first use."""
        if self._tool is None:
            import language_tool_python
            print("⏳ Loading LanguageTool grammar checker...")
            self._tool = language_tool_python.LanguageTool(self.language)
            print("✅ Grammar checker loaded!")
        return self._tool

    def correct(self, text: str) -> str:
        """Apply grammar corrections to text."""
        if not text:
            return text
        tool = self._load_tool()
        corrected = tool.correct(text)
        return corrected


class GramformerCorrector(GrammarCorrector):
    """Corrects grammar using Gramformer (AI-based transformer model, lazy-loaded)."""
    
    def __init__(self):
        self._model = None
    
    def _load_model(self):
        """Lazy-load Gramformer on first use."""
        if self._model is None:
            try:
                # Patch for transformers>=4.40 compatibility (use_auth_token -> token)
                import transformers
                original_from_pretrained = transformers.T5ForConditionalGeneration.from_pretrained
                def patched_from_pretrained(*args, **kwargs):
                    kwargs.pop('use_auth_token', None)
                    return original_from_pretrained(*args, **kwargs)
                transformers.T5ForConditionalGeneration.from_pretrained = patched_from_pretrained
                
                from gramformer import Gramformer
                import torch
                
                print("⏳ Loading Gramformer AI grammar checker...")
                torch.manual_seed(1212)
                # models=1 is the corrector model
                self._model = Gramformer(models=1, use_gpu=False)
                print("✅ Gramformer loaded!")
            except ImportError as e:
                print(f"⚠️  Gramformer not available: {e}", file=sys.stderr)
                print("   Install with: pip install -U git+https://github.com/PrithivirajDamodaran/Gramformer.git")
                # Fall back to pass-through
                self._model = "unavailable"
        return self._model
    
    def correct(self, text: str) -> str:
        """Apply AI-based grammar corrections to text."""
        if not text:
            return text
        
        model = self._load_model()
        if model == "unavailable":
            return text
        
        # Gramformer works best with individual sentences
        try:
            corrections = model.correct(text, max_candidates=1)
            if corrections:
                return list(corrections)[0]
        except Exception as e:
            print(f"⚠️  Gramformer error: {e}", file=sys.stderr)
        
        return text


def create_grammar_corrector(engine: str | None, language: str = "en") -> GrammarCorrector | None:
    """Factory function to create the appropriate grammar corrector."""
    if engine is None:
        return None
    
    engine = engine.lower()
    if engine == "languagetool":
        # Map short language codes to LanguageTool format
        lt_lang = f"{language}-US" if language == "en" else language
        return LanguageToolCorrector(language=lt_lang)
    elif engine == "gramformer":
        return GramformerCorrector()
    else:
        print(f"⚠️  Unknown grammar engine: {engine}", file=sys.stderr)
        return None


# =============================================================================
# Translation
# =============================================================================


class Translator(TextProcessor):
    """Abstract base class for translators."""
    
    @abstractmethod
    def translate(self, text: str) -> str:
        """Translate text to target language."""
        pass
    
    def process(self, text: str) -> str:
        """TextProcessor interface - delegates to translate()."""
        return self.translate(text)


class ArgosTranslator(Translator):
    """Translates text using Argos Translate (offline, open-source)."""
    
    def __init__(self, source_lang: str = "en", target_lang: str = "nl"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._translator = None
    
    def _load_translator(self):
        """Lazy-load Argos Translate on first use."""
        if self._translator is None:
            try:
                import argostranslate.package
                import argostranslate.translate
                
                print(f"⏳ Loading Argos Translate ({self.source_lang}→{self.target_lang})...")
                
                # Check if the required language package is installed
                installed_languages = argostranslate.translate.get_installed_languages()
                source = next((l for l in installed_languages if l.code == self.source_lang), None)
                target = next((l for l in installed_languages if l.code == self.target_lang), None)
                
                if source is None or target is None:
                    print(f"⚠️  Language pack not installed. Installing...")
                    self._install_language_pack()
                    installed_languages = argostranslate.translate.get_installed_languages()
                    source = next((l for l in installed_languages if l.code == self.source_lang), None)
                    target = next((l for l in installed_languages if l.code == self.target_lang), None)
                
                if source and target:
                    self._translator = source.get_translation(target)
                    if self._translator:
                        print("✅ Argos Translate loaded!")
                    else:
                        print(f"⚠️  No translation available for {self.source_lang}→{self.target_lang}")
                        self._translator = "unavailable"
                else:
                    print(f"⚠️  Language pack not found for {self.source_lang}→{self.target_lang}")
                    self._translator = "unavailable"
                    
            except ImportError as e:
                print(f"⚠️  Argos Translate not available: {e}", file=sys.stderr)
                print("   Install with: pip install argostranslate")
                self._translator = "unavailable"
        
        return self._translator
    
    def _install_language_pack(self):
        """Download and install the required language pack."""
        try:
            import argostranslate.package
            
            argostranslate.package.update_package_index()
            available_packages = argostranslate.package.get_available_packages()
            
            # Find the package for our language pair
            package = next(
                (p for p in available_packages 
                 if p.from_code == self.source_lang and p.to_code == self.target_lang),
                None
            )
            
            if package:
                print(f"   Downloading {self.source_lang}→{self.target_lang} package...")
                argostranslate.package.install_from_path(package.download())
                print("   ✅ Language pack installed!")
            else:
                print(f"   ⚠️  No package available for {self.source_lang}→{self.target_lang}")
        except Exception as e:
            print(f"   ⚠️  Failed to install language pack: {e}")
    
    def translate(self, text: str) -> str:
        """Translate text to target language."""
        if not text:
            return text
        
        translator = self._load_translator()
        if translator == "unavailable" or translator is None:
            return text
        
        try:
            # Clean up punctuation issues that can confuse Argos
            # (e.g., orphaned commas from filler removal: "Hello? , how are you")
            cleaned = re.sub(r'\?\s*,\s*', '? ', text)
            cleaned = re.sub(r'\.\s*,\s*', '. ', cleaned)
            cleaned = re.sub(r'!\s*,\s*', '! ', cleaned)
            cleaned = re.sub(r',\s*,', ',', cleaned)  # double commas
            cleaned = cleaned.strip()
            
            # Split into sentences to translate separately
            # Argos can truncate long multi-sentence text
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            
            translated_parts = []
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence:
                    translated = translator.translate(sentence)
                    if translated:
                        translated_parts.append(translated)
            
            return ' '.join(translated_parts) if translated_parts else text
        except Exception as e:
            print(f"⚠️  Translation error: {e}", file=sys.stderr)
            return text


# =============================================================================
# Audio Feedback
# =============================================================================


class AudioFeedback:
    """Provides audio feedback for recording start/stop."""
    
    # Frequencies for different events (Hz)
    START_FREQ = 800
    STOP_FREQ = 600

    # Distinct system sounds so start and stop are audibly different.
    START_SOUND = "/System/Library/Sounds/Tink.aiff"
    STOP_SOUND = "/System/Library/Sounds/Pop.aiff"
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._procs: list[subprocess.Popen] = []
    
    def play_start(self):
        """Play sound indicating recording started."""
        if self.enabled:
            self._play_beep(self.START_FREQ, duration=0.1)
    
    def play_stop(self):
        """Play sound indicating recording stopped."""
        if self.enabled:
            self._play_beep(self.STOP_FREQ, duration=0.15, sound=self.STOP_SOUND)
    
    def _play_beep(self, frequency: int, duration: float, sound: str | None = None):
        """Play a system sound without ever blocking the caller.

        `afplay` is fired and forgotten: waiting for it (as a blocking
        subprocess call) could stall the keyboard event-tap callback long
        enough for macOS to disable the tap, killing the hotkey.
        """
        try:
            # Reap finished players so a long session cannot accumulate
            # zombie processes.
            self._procs = [p for p in self._procs if p.poll() is None]
            self._procs.append(
                subprocess.Popen(
                    ["afplay", sound or self.START_SOUND],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        except Exception:
            # Silently fail if audio feedback doesn't work
            pass


# =============================================================================
# Text Typing
# =============================================================================


class TextTyper:
    """Types text into the currently focused application using macOS CGEvents."""

    def __init__(self):
        self.source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)

    def type_text(self, text: str):
        """Type text character by character into the focused app."""
        if not text:
            return

        for char in text:
            self._type_char(char)
            time.sleep(0.008)  # Small delay for reliability

    def _type_char(self, char: str):
        """Type a single Unicode character."""
        event_down = CGEventCreateKeyboardEvent(self.source, 0, True)
        event_up = CGEventCreateKeyboardEvent(self.source, 0, False)

        # Typing runs on a background thread, so the user may already be
        # holding modifiers again (e.g. starting the next dictation). Without
        # clearing the inherited flags those characters would be delivered as
        # keyboard shortcuts instead of text.
        CGEventSetFlags(event_down, 0)
        CGEventSetFlags(event_up, 0)

        CGEventKeyboardSetUnicodeString(event_down, len(char), char)
        CGEventKeyboardSetUnicodeString(event_up, len(char), char)

        CGEventPost(kCGHIDEventTap, event_down)
        CGEventPost(kCGHIDEventTap, event_up)


# =============================================================================
# Main Application
# =============================================================================


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
        self.transcriber = Transcriber(
            model_size=config.model_size,
            language=config.language,
            translate=config.translate_to_english,
            multilingual=config.multilingual,
            hotwords=config.hotwords,
        )
        self.typer = TextTyper()
        self.audio_feedback = AudioFeedback(enabled=config.audio_feedback)
        
        # Build text processing pipeline
        self.processors: list[TextProcessor] = []
        
        # 1. Filler removal (first, to clean up raw transcription)
        if config.remove_fillers:
            self.processors.append(FillerRemover())
        
        # 2. Snippet expansion
        if config.snippets:
            self.processors.append(SnippetExpander(config.snippets))
        
        # 3. Grammar correction
        self.grammar_corrector = create_grammar_corrector(
            config.grammar_engine,
            config.language or "en"
        )
        if self.grammar_corrector:
            self.processors.append(self.grammar_corrector)
        
        # 4. Translation (English → target language)
        self.translator: Translator | None = None
        if config.target_language:
            self.translator = ArgosTranslator(
                source_lang="en",
                target_lang=config.target_language
            )
            self.processors.append(self.translator)
        
        # Legacy compatibility
        self.enable_grammar = config.grammar_engine is not None

        # State
        self.is_recording = False
        self.running = True
        self.pressed_modifiers: set[str] = set()
        self.hotkey = config.hotkey
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
                self.pressed_modifiers.add(modifier)

                # Check if hotkey combo is pressed
                if self.hotkey.issubset(self.pressed_modifiers) and not self.is_recording:
                    self._start_recording()

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

                # If we were recording and hotkey released
                if self.is_recording and not self.hotkey.issubset(self.pressed_modifiers):
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
            if self.is_recording and not self.hotkey.issubset(actual):
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

        # Build hotkey display string
        hotkey_display = "+".join(k.capitalize() for k in sorted(self.hotkey))
        
        print("\n" + "=" * 60)
        print("🎙️  WHISPER DICTATION")
        print("=" * 60)
        print(f"Hold {hotkey_display} to record")
        print("Release to transcribe and type")
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


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Local speech-to-text dictation with grammar correction and translation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dictation.py                          # Basic dictation
  python dictation.py --grammar gramformer     # With AI grammar correction
  python dictation.py --multilingual           # Code-mixing (EN+Hindi+Dutch)
  python dictation.py --translate              # Any language → English
  python dictation.py --target-language nl     # English → Dutch translation
  python dictation.py --hotwords "OpenAI,Whisper,GitHub"
  python dictation.py --hotkey ctrl+shift      # Custom hotkey
        """
    )
    
    # Model settings
    parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--language", "-l",
        default="en",
        help="Language code (default: en). Use with caution when --multilingual is set.",
    )
    
    # Grammar correction
    parser.add_argument(
        "--grammar", "-g",
        choices=["languagetool", "gramformer"],
        default=None,
        help="Grammar correction engine (default: none)",
    )
    
    # Translation
    parser.add_argument(
        "--translate", "-t",
        action="store_true",
        help="Translate speech to English (Whisper's built-in translation)",
    )
    parser.add_argument(
        "--target-language", "-T",
        default=None,
        help="Translate English output to this language using Argos (e.g., 'nl' for Dutch)",
    )
    
    # Multilingual
    parser.add_argument(
        "--multilingual", "-M",
        action="store_true",
        help="Enable multilingual mode for code-mixing (e.g., English+Hindi+Dutch)",
    )
    
    # Text processing
    parser.add_argument(
        "--keep-fillers",
        action="store_true",
        help="Keep filler words (um, uh, like, etc.) in output",
    )
    parser.add_argument(
        "--hotwords", "-H",
        default=None,
        help="Comma-separated list of hotwords (proper nouns, jargon) for better recognition",
    )
    
    # Snippets
    parser.add_argument(
        "--snippets-file",
        default=None,
        help="Path to snippets file (format: trigger=text per line)",
    )
    
    # Audio feedback
    parser.add_argument(
        "--no-audio-feedback",
        action="store_true",
        help="Disable audio feedback beeps",
    )
    
    # Hotkey
    parser.add_argument(
        "--hotkey",
        default="cmd+shift",
        help="Hotkey combination (default: cmd+shift). Example: ctrl+shift",
    )
    
    args = parser.parse_args()

    try:
        config = DictationConfig.from_args(args)
    except ValueError as e:
        parser.error(str(e))

    print("⚠️  Requires Accessibility permissions for typing into apps.")
    print("   System Preferences → Security & Privacy → Privacy → Accessibility\n")

    exit_code = 0
    try:
        app = DictationApp(config=config)
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        exit_code = 1

    # PortAudio's atexit handler can block forever while terminating a stream,
    # which would leave a zombie process holding the hotkey. Everything of ours
    # is already cleaned up at this point, so exit hard.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    main()
