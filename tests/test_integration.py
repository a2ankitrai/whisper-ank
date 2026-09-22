"""Integration tests for the dictation pipeline."""

import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEndToEndFlow:
    """Test complete dictation flow from recording to typing."""

    @patch("dictation.CGEventPost")
    @patch("dictation.CGEventKeyboardSetUnicodeString")
    @patch("dictation.CGEventCreateKeyboardEvent")
    @patch("dictation.CGEventSourceCreate")
    @patch("dictation.WhisperModel")
    @patch("dictation.sd.InputStream")
    def test_full_dictation_flow(
        self,
        mock_input_stream,
        mock_whisper_model,
        mock_event_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
    ):
        """Test complete flow: record → transcribe → type."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        # Setup mocks
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_whisper_model.return_value = mock_model

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        # Create app
        app = DictationApp()

        # Recording start/stop runs on the app's worker thread
        import threading
        worker = threading.Thread(target=app._worker_loop, daemon=True)
        worker.start()

        # Simulate pressing hotkey
        app._on_press(Key.cmd)
        app._on_press(Key.shift)

        assert app.is_recording is True
        app.commands.join()

        # Simulate audio being recorded
        audio_data = np.sin(np.linspace(0, 2 * np.pi * 440, 16000)).astype(np.float32)
        app.recorder.audio_chunks = [audio_data.reshape(-1, 1)]

        # Release hotkey
        app._on_release(Key.cmd)

        # Wait for the worker to hand off, then for transcription to finish
        app.commands.join()
        app.wait_for_processing(timeout=5)
        app.running = False
        worker.join(timeout=2)

        # Verify text was typed (12 chars in "Hello world " including space)
        # Each char = 2 events (down + up)
        assert mock_create_event.call_count >= 20


class TestAudioToTranscriptionFlow:
    """Test audio recording to transcription flow."""

    @patch("dictation.WhisperModel")
    @patch("dictation.sd.InputStream")
    def test_recording_produces_valid_wav(
        self, mock_input_stream, mock_whisper_model
    ):
        """Test that recorded audio produces valid WAV for transcription."""
        from dictation import AudioRecorder

        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder(sample_rate=16000)
        recorder.start()

        # Simulate audio data
        audio = np.sin(np.linspace(0, 2 * np.pi * 440, 8000)).astype(np.float32)
        recorder.audio_chunks = [audio.reshape(-1, 1)]

        result = recorder.stop()

        # Should have correct length
        assert len(result) == 8000

        # Save and verify WAV is valid
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(result, path)

            # Verify WAV file is valid
            with wave.open(str(path), "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getframerate() == 16000
                assert wf.getnframes() == 8000
        finally:
            path.unlink(missing_ok=True)


class TestTranscriptionToTypingFlow:
    """Test transcription to typing flow."""

    @patch("dictation.time.sleep")
    @patch("dictation.CGEventPost")
    @patch("dictation.CGEventKeyboardSetUnicodeString")
    @patch("dictation.CGEventCreateKeyboardEvent")
    @patch("dictation.CGEventSourceCreate")
    def test_transcription_types_correctly(
        self,
        mock_event_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Test that transcribed text is typed correctly."""
        from dictation import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("Hello, world!")

        # Verify each character was typed
        expected_chars = list("Hello, world!")

        # Check unicode was set for each char (2 calls per char: down + up)
        unicode_calls = mock_set_unicode.call_args_list
        typed_chars = []
        for i in range(0, len(unicode_calls), 2):
            char = unicode_calls[i][0][2]
            typed_chars.append(char)

        assert typed_chars == expected_chars


class TestErrorRecovery:
    """Test error recovery scenarios."""

    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_recovers_from_transcription_error(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls
    ):
        """Should recover and be ready for next recording after error."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = np.zeros(16000, dtype=np.float32)
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.side_effect = [
            Exception("First call fails"),
            "Second call succeeds",
        ]
        mock_transcriber_cls.return_value = mock_transcriber

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()

        # First recording (will fail)
        app._process_recording()

        # App should still be functional
        assert app.running is True
        assert app.is_recording is False

        # Second recording (will succeed)
        app._process_recording()

        # Should have typed on second attempt
        mock_typer.type_text.assert_called_once_with("Second call succeeds ")

    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_recovers_from_audio_error(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls
    ):
        """Should recover from audio recording errors."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder.stop.side_effect = [
            Exception("Audio error"),
            np.zeros(16000, dtype=np.float32),
        ]
        mock_recorder_cls.return_value = mock_recorder

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = "Success"
        mock_transcriber_cls.return_value = mock_transcriber

        mock_typer = MagicMock()
        mock_typer_cls.return_value = mock_typer

        app = DictationApp()

        # First recording (will fail)
        try:
            app._process_recording()
        except Exception:
            pass  # Expected

        # App should still be functional for second attempt
        app._process_recording()

        mock_typer.type_text.assert_called_once_with("Success ")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_rapid_start_stop(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls
    ):
        """Should handle rapid start/stop cycles."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder.stop.return_value = None  # Too short
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()

        # Rapid cycles
        for _ in range(5):
            app._on_press(Key.cmd)
            app._on_press(Key.shift)
            app._on_release(Key.shift)
            app._on_release(Key.cmd)

        # Should not crash
        assert app.running is True

    @patch("dictation.TextTyper")
    @patch("dictation.Transcriber")
    @patch("dictation.AudioRecorder")
    def test_multiple_modifier_keys(
        self, mock_recorder_cls, mock_transcriber_cls, mock_typer_cls
    ):
        """Should handle multiple modifier key presses."""
        from dictation import DictationApp
        from pynput.keyboard import Key

        mock_recorder = MagicMock()
        mock_recorder_cls.return_value = mock_recorder

        app = DictationApp()

        # Press all modifiers
        app._on_press(Key.cmd)
        app._on_press(Key.shift)
        app._on_press(Key.ctrl)
        app._on_press(Key.alt)

        assert app.pressed_modifiers == {"cmd", "shift", "ctrl", "alt"}
        assert app.is_recording is True  # cmd+shift triggers recording

        # Release all
        app._on_release(Key.alt)
        app._on_release(Key.ctrl)
        app._on_release(Key.shift)
        app._on_release(Key.cmd)

        assert app.pressed_modifiers == set()

    @patch("dictation.time.sleep")
    @patch("dictation.CGEventPost")
    @patch("dictation.CGEventKeyboardSetUnicodeString")
    @patch("dictation.CGEventCreateKeyboardEvent")
    @patch("dictation.CGEventSourceCreate")
    def test_special_characters_typing(
        self,
        mock_event_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should correctly type special characters."""
        from dictation import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        special_text = "café résumé naïve"
        typer.type_text(special_text)

        # Verify unicode was set for each character
        assert mock_set_unicode.call_count == len(special_text) * 2

    @patch("dictation.time.sleep")
    @patch("dictation.CGEventPost")
    @patch("dictation.CGEventKeyboardSetUnicodeString")
    @patch("dictation.CGEventCreateKeyboardEvent")
    @patch("dictation.CGEventSourceCreate")
    def test_emoji_typing(
        self,
        mock_event_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should handle emoji characters."""
        from dictation import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        emoji_text = "👋🌍"
        typer.type_text(emoji_text)

        # Should attempt to type emoji (2 chars × 2 events)
        assert mock_create_event.call_count == 4
