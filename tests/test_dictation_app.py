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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_initializes_components(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should initialize recorder, transcriber, and typer."""
        from whisper_dictation.dictation_app import DictationApp

        app = DictationApp(model_size="tiny", language="en")

        mock_recorder_cls.assert_called_once()
        mock_typer_cls.assert_called_once()

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_default_state(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should initialize with correct default state."""
        from whisper_dictation.dictation_app import DictationApp

        app = DictationApp()

        assert app.is_recording is False
        assert app.running is True
        assert app.pressed_modifiers == set()
        assert app.hotkey == {"cmd", "shift"}

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_uses_provided_model_size(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should pass model size to transcriber."""
        from whisper_dictation.dictation_app import DictationApp

        DictationApp(model_size="large-v3")

        # Verify transcriber was called with correct model size
        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["model_size"] == "large-v3"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_uses_provided_language(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should pass language to transcriber."""
        from whisper_dictation.dictation_app import DictationApp

        DictationApp(language="de")

        # Verify transcriber was called with correct language
        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["language"] == "de"


class TestDictationAppKeyToModifier:
    """Test key to modifier conversion."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_cmd_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map cmd keys to 'cmd'."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.cmd) == "cmd"
        assert app._key_to_modifier(Key.cmd_l) == "cmd"
        assert app._key_to_modifier(Key.cmd_r) == "cmd"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_shift_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map shift keys to 'shift'."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.shift) == "shift"
        assert app._key_to_modifier(Key.shift_l) == "shift"
        assert app._key_to_modifier(Key.shift_r) == "shift"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_ctrl_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map ctrl keys to 'ctrl'."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.ctrl) == "ctrl"
        assert app._key_to_modifier(Key.ctrl_l) == "ctrl"
        assert app._key_to_modifier(Key.ctrl_r) == "ctrl"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_alt_key_mapping(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should map alt keys to 'alt'."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()

        assert app._key_to_modifier(Key.alt) == "alt"
        assert app._key_to_modifier(Key.alt_l) == "alt"
        assert app._key_to_modifier(Key.alt_r) == "alt"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_non_modifier_returns_none(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should return None for non-modifier keys."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key, KeyCode

        app = DictationApp()

        assert app._key_to_modifier(Key.space) is None
        assert app._key_to_modifier(Key.enter) is None
        assert app._key_to_modifier(KeyCode.from_char("a")) is None


class TestDictationAppOnPress:
    """Test key press handling."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_adds_modifier_to_pressed_set(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should add pressed modifier to set."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app._on_press(Key.cmd)

        assert "cmd" in app.pressed_modifiers

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_starts_recording_when_hotkey_pressed(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should start recording when hotkey combo is pressed."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_does_not_restart_if_already_recording(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not restart recording if already recording."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_escape_sets_running_false(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should set running to False when escape pressed."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        result = app._on_press(Key.esc)

        assert app.running is False
        assert result is False  # Should return False to stop listener

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_partial_hotkey_does_not_start(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not start recording with only partial hotkey."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._on_press(Key.cmd)  # Only cmd, not shift

        assert app.is_recording is False
        mock_recorder.start.assert_not_called()


class TestDictationAppOnRelease:
    """Test key release handling."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_removes_modifier_from_pressed_set(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should remove released modifier from set."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp()
        app.pressed_modifiers = {"cmd", "shift"}
        app._on_release(Key.cmd)

        assert "cmd" not in app.pressed_modifiers
        assert "shift" in app.pressed_modifiers

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_triggers_processing_when_hotkey_released(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should trigger processing when hotkey released while recording."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_does_not_process_if_not_recording(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should not process if not recording."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_handles_no_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle case where no audio was recorded."""
        from whisper_dictation.dictation_app import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = None
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._process_recording()

        # Should not crash, transcriber should not be called
        mock_transcriber_cls.return_value.transcribe.assert_not_called()

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_handles_short_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should skip very short recordings."""
        from whisper_dictation.dictation_app import DictationApp

        mock_recorder = MagicMock()
        # Less than 0.2 seconds at 16kHz (3200 samples)
        mock_recorder.stop.return_value = np.zeros(1000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()
        app._process_recording()

        # Should not transcribe
        mock_transcriber_cls.return_value.transcribe.assert_not_called()

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_transcribes_and_types_valid_audio(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should transcribe and type valid audio."""
        from whisper_dictation.dictation_app import DictationApp

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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_handles_empty_transcription(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle empty transcription result."""
        from whisper_dictation.dictation_app import DictationApp

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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_handles_transcription_error(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle transcription errors gracefully."""
        from whisper_dictation.dictation_app import DictationApp

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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_cleans_up_temp_file(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should clean up temporary WAV file."""
        from whisper_dictation.dictation_app import DictationApp

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


class TestDictationAppToggleMode:
    """Test toggle recording mode (press once to start, press again to stop)."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_first_full_press_starts_recording(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Pressing the full combo once should start recording."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp(config=DictationConfig(recording_mode="toggle"))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)

        assert app.is_recording is True

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_release_does_not_stop_recording(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Releasing keys in toggle mode must not stop the recording."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp(config=DictationConfig(recording_mode="toggle"))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)
        app._on_release(Key.cmd)
        app._on_release(Key.shift)

        assert app.is_recording is True

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_second_full_press_stops_recording(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Pressing the full combo again should stop the recording."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp(config=DictationConfig(recording_mode="toggle"))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)
        app._on_release(Key.cmd)
        app._on_release(Key.shift)

        app._on_press(Key.cmd)
        app._on_press(Key.shift)

        assert app.is_recording is False

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_holding_combo_does_not_retrigger(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """A repeated press of an already-held modifier must not re-toggle."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key

        app = DictationApp(config=DictationConfig(recording_mode="toggle"))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)  # rising edge: start
        app._on_press(Key.shift)  # still held: must not toggle again

        assert app.is_recording is True


class TestDictationAppReplay:
    """Test the replay hotkey and transcription history."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_replay_types_last_history_entry(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should retype the most recent transcription."""
        from whisper_dictation.dictation_app import DictationApp

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()
        app.history.extend(["first", "second"])

        app._replay_last()

        mock_typer.type_text.assert_called_once_with("second ")

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_replay_with_empty_history_does_not_type(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Should not call the typer when there is nothing to replay."""
        from whisper_dictation.dictation_app import DictationApp

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()
        app._replay_last()

        mock_typer.type_text.assert_not_called()

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_history_evicts_oldest_past_ten(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """History should only keep the last 10 transcriptions."""
        from whisper_dictation.dictation_app import DictationApp

        app = DictationApp()
        for i in range(12):
            app.history.append(f"item{i}")

        assert len(app.history) == 10
        assert list(app.history) == [f"item{i}" for i in range(2, 12)]

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_process_recording_appends_to_history(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """A successful transcription should be recorded in history."""
        from whisper_dictation.dictation_app import DictationApp

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = "Hello world"
        mock_transcriber_cls.return_value = mock_transcriber

        app = DictationApp()
        app._process_recording()

        assert list(app.history) == ["Hello world"]

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_replay_hotkey_queues_replay_command(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Pressing the replay combo should queue a replay command."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key, KeyCode

        # Distinct record hotkey so it can't also fire "start" here.
        app = DictationApp(config=DictationConfig(hotkey={"ctrl", "alt"}))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)
        app._on_press(KeyCode.from_char("v"))

        assert app.commands.get_nowait() == "replay"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_non_replay_key_does_not_queue_replay(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """A different key under the same modifiers should not trigger replay."""
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import Key, KeyCode

        app = DictationApp(config=DictationConfig(hotkey={"ctrl", "alt"}))
        app._on_press(Key.cmd)
        app._on_press(Key.shift)
        app._on_press(KeyCode.from_char("x"))

        assert app.commands.empty()

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_replay_key_without_modifiers_does_not_queue_replay(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """The replay key alone, without its modifiers, must not trigger replay."""
        from whisper_dictation.dictation_app import DictationApp
        from pynput.keyboard import KeyCode

        app = DictationApp()
        app._on_press(KeyCode.from_char("v"))

        assert app.commands.empty()


class TestDictationAppApplyConfig:
    """Tests for apply_config() (live settings updates)."""

    def _make_app(self, **config_kwargs):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp

        with patch("whisper_dictation.dictation_app.AudioFeedback"), \
             patch("whisper_dictation.dictation_app.TextTyper"), \
             patch("whisper_dictation.dictation_app.Transcriber"), \
             patch("whisper_dictation.dictation_app.AudioRecorder"):
            return DictationApp(config=DictationConfig(**config_kwargs))

    def test_updates_hotkey_recording_mode_and_replay_hotkey(self):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        new_config = DictationConfig(
            hotkey={"ctrl", "alt"},
            recording_mode="toggle",
            replay_hotkey=(frozenset({"ctrl"}), "r"),
        )

        with patch("whisper_dictation.dictation_app.Transcriber"):
            app.apply_config(new_config)

        assert app.hotkey == {"ctrl", "alt"}
        assert app.recording_mode == "toggle"
        assert app.replay_hotkey == (frozenset({"ctrl"}), "r")
        assert app.config == new_config

    def test_updates_audio_feedback_enabled_flag(self):
        from whisper_dictation.config import DictationConfig

        app = self._make_app(audio_feedback=True)
        new_config = DictationConfig(audio_feedback=False)

        with patch("whisper_dictation.dictation_app.Transcriber"):
            app.apply_config(new_config)

        assert app.audio_feedback.enabled is False

    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_rebuilds_transcriber_with_new_model_settings(self, mock_transcriber_cls):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        new_config = DictationConfig(model_size="large-v3", language="nl")

        app.apply_config(new_config)

        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["model_size"] == "large-v3"
        assert call_kwargs["language"] == "nl"

    @patch("whisper_dictation.dictation_app.create_grammar_corrector")
    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_rebuilds_grammar_corrector(self, mock_transcriber_cls, mock_create_corrector):
        from whisper_dictation.config import DictationConfig

        mock_corrector = MagicMock()
        mock_create_corrector.return_value = mock_corrector
        app = self._make_app()
        new_config = DictationConfig(grammar_engine="languagetool")

        app.apply_config(new_config)

        assert app.grammar_corrector is mock_corrector
        assert mock_corrector in app.processors

    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_invalid_new_config_leaves_previous_state_untouched(self, mock_transcriber_cls):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        original_transcriber = app.transcriber
        mock_transcriber_cls.side_effect = ValueError("boom")
        new_config = DictationConfig(model_size="not-a-real-model")

        with pytest.raises(ValueError):
            app.apply_config(new_config)

        assert app.transcriber is original_transcriber
        assert app.hotkey == {"cmd", "shift"}  # unchanged, not the new_config's
        assert app.config.model_size == "base"  # unchanged

    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_non_pipeline_field_change_skips_transcriber_rebuild(
        self, mock_transcriber_cls
    ):
        """A trivial toggle like recording_mode must not reload the model.

        Transcriber.__init__ eagerly loads the Whisper model; rebuilding it
        on every apply_config() call would freeze the Cocoa main thread on
        quick menu-bar toggles (see MenuBarApp._toggle_recording_mode).
        """
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        new_config = DictationConfig(recording_mode="toggle")

        app.apply_config(new_config)

        mock_transcriber_cls.assert_not_called()
        assert app.recording_mode == "toggle"
        assert app.config == new_config


class TestDictationAppBackgroundLifecycle:
    """Tests for start_background()/poll_health() (GUI/headless shared plumbing)."""

    def _make_app(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp

        with patch("whisper_dictation.dictation_app.AudioFeedback"), \
             patch("whisper_dictation.dictation_app.TextTyper"), \
             patch("whisper_dictation.dictation_app.Transcriber"), \
             patch("whisper_dictation.dictation_app.AudioRecorder"):
            return DictationApp(config=DictationConfig())

    @patch("whisper_dictation.dictation_app._resilient_listener_class")
    def test_start_background_starts_worker_and_listener(self, mock_listener_cls):
        app = self._make_app()
        fake_listener = MagicMock()
        fake_listener.running = True
        mock_listener_cls.return_value = MagicMock(return_value=fake_listener)

        app.start_background()
        try:
            assert app.worker.is_alive()
            assert app.listener is fake_listener
            fake_listener.start.assert_called_once()
            fake_listener.wait.assert_called_once()
        finally:
            app.running = False
            app.worker.join(timeout=2)

    @patch("whisper_dictation.dictation_app.live_modifiers", return_value=set())
    @patch("whisper_dictation.dictation_app._resilient_listener_class")
    def test_poll_health_rebuilds_dead_listener(self, mock_listener_cls, mock_live_modifiers):
        app = self._make_app()
        dead_listener = MagicMock()
        dead_listener.running = False
        new_listener = MagicMock()
        new_listener.running = True
        mock_listener_cls.return_value = MagicMock(side_effect=[new_listener])
        app.listener = dead_listener
        app.listener_started_at = time.monotonic()

        app.poll_health()

        dead_listener.stop.assert_called_once()
        assert app.listener is new_listener
        new_listener.start.assert_called_once()

    @patch("whisper_dictation.dictation_app.live_modifiers", return_value=set())
    def test_poll_health_warns_on_stalled_command(self, mock_live_modifiers, capsys):
        app = self._make_app()
        alive_listener = MagicMock()
        alive_listener.running = True
        alive_listener.ensure_tap_enabled.return_value = False
        app.listener = alive_listener
        app.listener_started_at = time.monotonic()
        app.command_started_at = (time.monotonic() - 6, "start")

        app.poll_health()

        captured = capsys.readouterr()
        assert "stuck for" in captured.err


class TestDictationAppThreadSafety:
    """Test thread safety of DictationApp."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_concurrent_key_presses(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle concurrent key presses safely."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_concurrent_releases(self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls):
        """Should handle concurrent key releases safely."""
        from whisper_dictation.dictation_app import DictationApp
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

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_resync_stops_recording_after_missed_release(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """A missed key release must not leave the app stuck in recording."""
        from whisper_dictation.dictation_app import DictationApp

        app = DictationApp()
        app.is_recording = True
        app.pressed_modifiers = {"cmd", "shift"}

        with patch("whisper_dictation.dictation_app.live_modifiers", return_value=set()):
            app._resync_modifiers()

        assert app.pressed_modifiers == set()
        assert app.is_recording is False
        assert app.commands.get_nowait() == "stop"

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_resync_keeps_recording_while_hotkey_held(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Recording must continue while the hotkey is physically held."""
        from whisper_dictation.dictation_app import DictationApp

        app = DictationApp()
        app.is_recording = True
        app.pressed_modifiers = {"cmd"}

        with patch("whisper_dictation.dictation_app.live_modifiers", return_value={"cmd", "shift"}):
            app._resync_modifiers()

        assert app.pressed_modifiers == {"cmd", "shift"}
        assert app.is_recording is True
        assert app.commands.empty()

    def test_listener_reenables_disabled_tap(self):
        """A tap disabled by macOS should be switched back on."""
        import whisper_dictation.keyboard as keyboard_module

        listener_cls = keyboard_module._resilient_listener_class()
        listener = listener_cls(on_press=lambda k: None, on_release=lambda k: None)
        listener._event_tap = object()

        with patch("whisper_dictation.keyboard.CGEventTapIsEnabled", return_value=False) as is_enabled, \
             patch("whisper_dictation.keyboard.CGEventTapEnable") as enable:
            assert listener.ensure_tap_enabled() is True
            enable.assert_called_once_with(listener._event_tap, True)

    def test_listener_leaves_healthy_tap_alone(self):
        """A healthy tap should not be touched."""
        import whisper_dictation.keyboard as keyboard_module

        listener_cls = keyboard_module._resilient_listener_class()
        listener = listener_cls(on_press=lambda k: None, on_release=lambda k: None)
        listener._event_tap = object()

        with patch("whisper_dictation.keyboard.CGEventTapIsEnabled", return_value=True), \
             patch("whisper_dictation.keyboard.CGEventTapEnable") as enable:
            assert listener.ensure_tap_enabled() is False
            enable.assert_not_called()


class TestDictationAppDoesNotStall:
    """A slow or hung transcription must never block the next recording."""

    @patch("whisper_dictation.dictation_app.AudioFeedback")
    @patch("whisper_dictation.dictation_app.TextTyper")
    @patch("whisper_dictation.dictation_app.Transcriber")
    @patch("whisper_dictation.dictation_app.AudioRecorder")
    def test_slow_transcription_does_not_block_next_recording(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls, mock_feedback_cls
    ):
        """Recording N+1 must start even while recording N is still processing."""
        from whisper_dictation.dictation_app import DictationApp
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
