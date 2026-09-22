"""Tests for DictationApp class."""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def run_worker(app, timeout=2.0):
    """Run the app's command worker until all queued commands are handled."""
    worker = threading.Thread(target=app._worker_loop, daemon=True)
    worker.start()
    try:
        app.commands.join()
    finally:
        app.running = False
        worker.join(timeout=timeout)



class TestDictationAppInit:
    """Test DictationApp initialization."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_initializes_components(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should initialize recorder, transcriber, and typer."""
        from dictation import DictationApp

        app = DictationApp(model_size="tiny", language="en")

        mock_recorder_cls.assert_called_once()
        mock_typer_cls.assert_called_once()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_default_state(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should initialize with correct default state."""
        from dictation import DictationApp

        app = DictationApp()

        assert app.is_recording is False
        assert app.running is True
        assert app.pressed_modifiers == set()
        assert app.hotkey == {"cmd", "shift"}

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_uses_provided_model_size(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should pass model size to transcriber."""
        from dictation import DictationApp

        DictationApp(model_size="large-v3")

        # Verify transcriber was called with correct model size
        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["model_size"] == "large-v3"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_uses_provided_language(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should pass language to transcriber."""
        from dictation import DictationApp

        DictationApp(language="de")

        # Verify transcriber was called with correct language
        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["language"] == "de"


class TestDictationAppKeyToModifier:
    """Test key to modifier conversion."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_cmd_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map cmd keys to 'cmd'."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.cmd) == "cmd"
        assert app._key_to_modifier(Key.cmd_l) == "cmd"
        assert app._key_to_modifier(Key.cmd_r) == "cmd"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_shift_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map shift keys to 'shift'."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.shift) == "shift"
        assert app._key_to_modifier(Key.shift_l) == "shift"
        assert app._key_to_modifier(Key.shift_r) == "shift"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_ctrl_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map ctrl keys to 'ctrl'."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.ctrl) == "ctrl"
        assert app._key_to_modifier(Key.ctrl_l) == "ctrl"
        assert app._key_to_modifier(Key.ctrl_r) == "ctrl"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_alt_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map alt keys to 'alt'."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.alt) == "alt"
        assert app._key_to_modifier(Key.alt_l) == "alt"
        assert app._key_to_modifier(Key.alt_r) == "alt"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_non_modifier_returns_none(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should return None for non-modifier keys."""
        from dictation import DictationApp
        from pynput.keyboard import Key, KeyCode

        app = DictationApp()

        assert app._key_to_modifier(Key.space) is None
        assert app._key_to_modifier(Key.enter) is None
        assert app._key_to_modifier(KeyCode.from_char("a")) is None


class TestDictationAppOnPress:
    """Test key press handling."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_adds_modifier_to_pressed_set(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should add pressed modifier to set."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app._on_press(Key.cmd)

        assert "cmd" in app.pressed_modifiers

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_starts_recording_when_hotkey_pressed(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should start recording when hotkey combo is pressed."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._on_press(Key.cmd)
        app._on_press(Key.shift)

        assert app.is_recording is True
        # The heavy work is queued for the worker thread, never done inline
        run_worker(app)
        mock_recorder.start.assert_called_once()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_does_not_restart_if_already_recording(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not restart recording if already recording."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._on_press(Key.cmd)
        app._on_press(Key.shift)  # Start recording
        app._on_press(Key.shift)  # Press shift again
        run_worker(app)

        # Should only start once
        assert mock_recorder.start.call_count == 1

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_escape_sets_running_false(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should set running to False when escape pressed."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        result = app._on_press(Key.esc)

        assert app.running is False
        assert result is False  # Should return False to stop listener

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_partial_hotkey_does_not_start(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not start recording with only partial hotkey."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._on_press(Key.cmd)  # Only cmd, not shift

        assert app.is_recording is False
        mock_recorder.start.assert_not_called()


class TestDictationAppOnRelease:
    """Test key release handling."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_removes_modifier_from_pressed_set(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should remove released modifier from set."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app.pressed_modifiers = {"cmd", "shift"}
        app._on_release(Key.cmd)

        assert "cmd" not in app.pressed_modifiers
        assert "shift" in app.pressed_modifiers

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_triggers_processing_when_hotkey_released(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should trigger processing when hotkey released while recording."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app.is_recording = True
        app.pressed_modifiers = {"cmd", "shift"}

        with patch.object(app, "_process_recording") as mock_process:
            app._on_release(Key.cmd)

            # Should have started processing thread
            time.sleep(0.1)  # Give thread time to start
            # is_recording should be False
            assert app.is_recording is False

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_does_not_process_if_not_recording(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not process if not recording."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app.is_recording = False
        app.pressed_modifiers = {"cmd", "shift"}

        with patch.object(app, "_process_recording") as mock_process:
            app._on_release(Key.cmd)
            time.sleep(0.1)

            # Should not process since not recording
            # (We can't easily verify thread wasn't started, but state should be unchanged)
            assert app.is_recording is False


class TestDictationAppProcessRecording:
    """Test recording processing."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_handles_no_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle case where no audio was recorded."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = None
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._process_recording()

        # Should not crash, transcriber should not be called
        mock_transcriber_cls.return_value.transcribe.assert_not_called()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_handles_short_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should skip very short recordings."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        # Less than 0.2 seconds at 16kHz (3200 samples)
        mock_recorder.stop.return_value = np.zeros(1000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._process_recording()

        # Should not transcribe
        mock_transcriber_cls.return_value.transcribe.assert_not_called()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_transcribes_and_types_valid_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should transcribe and type valid audio."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)  # 1 second
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = "Hello world"
        mock_transcriber_cls.return_value = mock_transcriber

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()
        app._process_recording()

        # Should transcribe
        mock_transcriber.transcribe.assert_called_once()
        # Should type result with trailing space
        mock_typer.type_text.assert_called_once_with("Hello world ")

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_handles_empty_transcription(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle empty transcription result."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = ""
        mock_transcriber_cls.return_value = mock_transcriber

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()
        app._process_recording()

        # Should not type anything
        mock_typer.type_text.assert_not_called()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_handles_transcription_error(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle transcription errors gracefully."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.side_effect = Exception("Transcription failed")
        mock_transcriber_cls.return_value = mock_transcriber

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()
        # Should not raise exception
        app._process_recording()

        # Should not type anything
        mock_typer.type_text.assert_not_called()

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_cleans_up_temp_file(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should clean up temporary WAV file."""
        from dictation import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = "test"
        mock_transcriber_cls.return_value = mock_transcriber

        app = DictationApp()

        # Track temp files created
        created_files = []
        original_save = mock_recorder.save_wav

        def track_save(audio, path):
            created_files.append(path)
            # Create an actual file so we can verify it's deleted
            path.touch()

        mock_recorder.save_wav = track_save

        app._process_recording()

        # Temp file should be deleted
        for f in created_files:
            assert not f.exists()


class TestDictationAppThreadSafety:
    """Test thread safety of DictationApp."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_concurrent_key_presses(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle concurrent key presses safely."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        # Simulate rapid concurrent key presses
        threads = []
        for _ in range(10):
            t1 = threading.Thread(target=lambda: app._on_press(Key.cmd))
            t2 = threading.Thread(target=lambda: app._on_press(Key.shift))
            threads.extend([t1, t2])

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should not crash and modifiers should be in set
        assert "cmd" in app.pressed_modifiers
        assert "shift" in app.pressed_modifiers

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_concurrent_releases(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle concurrent key releases safely."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app.pressed_modifiers = {"cmd", "shift", "ctrl", "alt"}

        threads = []
        for key in [Key.cmd, Key.shift, Key.ctrl, Key.alt]:
            t = threading.Thread(target=lambda k=key: app._on_release(k))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should not crash and all modifiers should be removed
        assert len(app.pressed_modifiers) == 0


class TestDictationAppRecovery:
    """Tests for hotkey resilience: stale key state and disabled event taps."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_resync_stops_recording_after_missed_release(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """A missed key release must not leave the app stuck in recording."""
        from dictation import DictationApp

        app = DictationApp()
        app.is_recording = True
        app.pressed_modifiers = {"cmd", "shift"}

        with patch("dictation.live_modifiers", return_value=set()):
            app._resync_modifiers()

        assert app.pressed_modifiers == set()
        assert app.is_recording is False
        assert app.commands.get_nowait() == "stop"

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_resync_keeps_recording_while_hotkey_held(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Recording must continue while the hotkey is physically held."""
        from dictation import DictationApp

        app = DictationApp()
        app.is_recording = True
        app.pressed_modifiers = {"cmd"}

        with patch("dictation.live_modifiers", return_value={"cmd", "shift"}):
            app._resync_modifiers()

        assert app.pressed_modifiers == {"cmd", "shift"}
        assert app.is_recording is True
        assert app.commands.empty()

    def test_listener_reenables_disabled_tap(self):
        """A tap disabled by macOS should be switched back on."""
        import dictation

        listener_cls = dictation._resilient_listener_class()
        listener = listener_cls(on_press=lambda k: None, on_release=lambda k: None)
        listener._event_tap = object()

        with patch("dictation.CGEventTapIsEnabled", return_value=False) as is_enabled, \
             patch("dictation.CGEventTapEnable") as enable:
            assert listener.ensure_tap_enabled() is True
            enable.assert_called_once_with(listener._event_tap, True)

    def test_listener_leaves_healthy_tap_alone(self):
        """A healthy tap should not be touched."""
        import dictation

        listener_cls = dictation._resilient_listener_class()
        listener = listener_cls(on_press=lambda k: None, on_release=lambda k: None)
        listener._event_tap = object()

        with patch("dictation.CGEventTapIsEnabled", return_value=True), \
             patch("dictation.CGEventTapEnable") as enable:
            assert listener.ensure_tap_enabled() is False
            enable.assert_not_called()


class TestDictationAppDoesNotStall:
    """A slow or hung transcription must never block the next recording."""

    @patch("dictation.AudioFeedback")
    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_slow_transcription_does_not_block_next_recording(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Recording N+1 must start even while recording N is still processing."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()

        # First transcription hangs forever
        hang = threading.Event()
        with patch.object(app, "_process_recording", side_effect=lambda audio=None: hang.wait(30)):
            worker = threading.Thread(target=app._worker_loop, daemon=True)
            worker.start()
            try:
                app._on_press(Key.cmd)
                app._on_press(Key.shift)
                app._on_release(Key.cmd)

                # Second recording while the first one is still "processing"
                app._on_press(Key.cmd)

                deadline = time.time() + 3
                while mock_recorder.start.call_count < 2 and time.time() < deadline:
                    time.sleep(0.02)

                assert mock_recorder.start.call_count == 2
            finally:
                hang.set()
                app.running = False
                worker.join(timeout=2)
