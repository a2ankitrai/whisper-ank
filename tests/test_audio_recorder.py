"""Tests for AudioRecorder class."""

import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dictation import AudioRecorder


class TestAudioRecorderInit:
    """Test AudioRecorder initialization."""

    def test_default_sample_rate(self):
        """Should use 16000 Hz sample rate by default."""
        recorder = AudioRecorder()
        assert recorder.sample_rate == 16000

    def test_custom_sample_rate(self):
        """Should accept custom sample rate."""
        recorder = AudioRecorder(sample_rate=44100)
        assert recorder.sample_rate == 44100

    def test_initial_state(self):
        """Should initialize with correct default state."""
        recorder = AudioRecorder()
        assert recorder.recording is False
        assert recorder.audio_chunks == []
        assert recorder.stream is None


class TestAudioRecorderStartStop:
    """Test AudioRecorder start/stop functionality."""

    @patch("dictation.sd.InputStream")
    def test_start_sets_recording_flag(self, mock_input_stream):
        """Should set recording flag to True when started."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()

        assert recorder.recording is True
        mock_stream.start.assert_called_once()

    @patch("dictation.sd.InputStream")
    def test_start_clears_previous_chunks(self, mock_input_stream):
        """Should clear audio chunks when starting new recording."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.audio_chunks = [np.array([1, 2, 3])]
        recorder.start()

        assert recorder.audio_chunks == []

    @patch("dictation.sd.InputStream")
    def test_start_creates_input_stream(self, mock_input_stream):
        """Should create InputStream with correct parameters."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder(sample_rate=16000)
        recorder.start()

        mock_input_stream.assert_called_once()
        call_kwargs = mock_input_stream.call_args[1]
        assert call_kwargs["samplerate"] == 16000
        assert call_kwargs["channels"] == 1
        assert call_kwargs["dtype"] == "float32"

    @patch("dictation.sd.InputStream")
    def test_stop_returns_none_when_no_audio(self, mock_input_stream):
        """Should return None when no audio was recorded."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()
        result = recorder.stop()

        assert result is None

    @patch("dictation.sd.InputStream")
    def test_stop_returns_concatenated_audio(self, mock_input_stream):
        """Should return concatenated audio data."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()

        # Simulate audio callback adding chunks
        recorder.audio_chunks = [
            np.array([[0.1], [0.2]], dtype=np.float32),
            np.array([[0.3], [0.4]], dtype=np.float32),
        ]

        result = recorder.stop()

        assert result is not None
        assert len(result) == 4
        np.testing.assert_array_almost_equal(result, [0.1, 0.2, 0.3, 0.4])

    @patch("dictation.sd.InputStream")
    def test_stop_keeps_stream_open(self, mock_input_stream):
        """Stop must not tear the stream down.

        Closing a CoreAudio stream per recording could deadlock inside
        PortAudio and kill the hotkey until the app was restarted.
        """
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()
        recorder.stop()

        mock_stream.abort.assert_not_called()
        mock_stream.close.assert_not_called()
        assert recorder.stream is mock_stream

    @patch("dictation.sd.InputStream")
    def test_reuses_single_stream_across_recordings(self, mock_input_stream):
        """Repeated recordings should reuse one long-lived stream."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        for _ in range(3):
            recorder.start()
            recorder.stop()

        assert mock_input_stream.call_count == 1
        assert mock_stream.start.call_count == 1

    @patch("dictation.sd.InputStream")
    def test_replaces_dead_stream(self, mock_input_stream):
        """A stream that went inactive (device unplugged) is replaced."""
        dead_stream = MagicMock()
        dead_stream.active = False
        fresh_stream = MagicMock()
        fresh_stream.active = True
        mock_input_stream.side_effect = [dead_stream, fresh_stream]

        recorder = AudioRecorder()
        recorder.start()
        recorder.stop()
        recorder.start()

        assert recorder.stream is fresh_stream
        assert mock_input_stream.call_count == 2

    @patch("dictation.sd.InputStream")
    def test_close_survives_hanging_stream(self, mock_input_stream):
        """A stream that never returns must not block shutdown."""
        import threading
        import time

        block = threading.Event()
        mock_stream = MagicMock()
        mock_stream.abort.side_effect = lambda: block.wait(30)
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()

        try:
            started = time.monotonic()
            recorder.close()
            elapsed = time.monotonic() - started

            assert elapsed < 5
            assert recorder.stream is None
        finally:
            block.set()

    @patch("dictation.sd.InputStream")
    def test_stop_sets_recording_flag_false(self, mock_input_stream):
        """Should set recording flag to False when stopped."""
        mock_stream = MagicMock()
        mock_input_stream.return_value = mock_stream

        recorder = AudioRecorder()
        recorder.start()
        recorder.stop()

        assert recorder.recording is False


class TestAudioRecorderCallback:
    """Test AudioRecorder audio callback."""

    @patch("dictation.sd.InputStream")
    def test_callback_stores_audio_when_recording(self, mock_input_stream):
        """Should store audio data when recording."""
        recorder = AudioRecorder()
        recorder.recording = True

        indata = np.array([[0.5], [0.6]], dtype=np.float32)
        recorder._audio_callback(indata, 2, None, None)

        assert len(recorder.audio_chunks) == 1
        np.testing.assert_array_equal(recorder.audio_chunks[0], indata)

    @patch("dictation.sd.InputStream")
    def test_callback_ignores_audio_when_not_recording(self, mock_input_stream):
        """Should ignore audio data when not recording."""
        recorder = AudioRecorder()
        recorder.recording = False

        indata = np.array([[0.5], [0.6]], dtype=np.float32)
        recorder._audio_callback(indata, 2, None, None)

        assert len(recorder.audio_chunks) == 0

    @patch("dictation.sd.InputStream")
    def test_callback_copies_data(self, mock_input_stream):
        """Should make a copy of audio data, not reference."""
        recorder = AudioRecorder()
        recorder.recording = True

        indata = np.array([[0.5], [0.6]], dtype=np.float32)
        recorder._audio_callback(indata, 2, None, None)

        # Modify original
        indata[0] = 999

        # Stored copy should be unchanged
        assert recorder.audio_chunks[0][0] != 999


class TestAudioRecorderSaveWav:
    """Test AudioRecorder WAV file saving."""

    def test_save_wav_creates_file(self):
        """Should create a valid WAV file."""
        recorder = AudioRecorder(sample_rate=16000)
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(audio, path)
            assert path.exists()
            assert path.stat().st_size > 0
        finally:
            path.unlink(missing_ok=True)

    def test_save_wav_correct_format(self):
        """Should save with correct WAV parameters."""
        recorder = AudioRecorder(sample_rate=16000)
        audio = np.array([0.0, 0.5, -0.5], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(audio, path)

            with wave.open(str(path), "rb") as wf:
                assert wf.getnchannels() == 1
                assert wf.getsampwidth() == 2  # 16-bit
                assert wf.getframerate() == 16000
                assert wf.getnframes() == 3
        finally:
            path.unlink(missing_ok=True)

    def test_save_wav_preserves_audio_values(self):
        """Should preserve audio values when saving."""
        recorder = AudioRecorder(sample_rate=16000)
        # Use values that won't lose precision in int16 conversion
        audio = np.array([0.0, 0.5, -0.5], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(audio, path)

            with wave.open(str(path), "rb") as wf:
                frames = wf.readframes(3)
                loaded = np.frombuffer(frames, dtype=np.int16) / 32767

            np.testing.assert_array_almost_equal(audio, loaded, decimal=3)
        finally:
            path.unlink(missing_ok=True)

    def test_save_wav_clips_out_of_range_samples(self):
        """Should clamp rather than wrap samples outside [-1, 1].

        Wrapping would turn a loud passage into noise Whisper cannot read.
        """
        recorder = AudioRecorder(sample_rate=16000)
        audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(audio, path)

            with wave.open(str(path), "rb") as wf:
                loaded = np.frombuffer(wf.readframes(3), dtype=np.int16)

            assert loaded[0] == 32767
            assert loaded[1] == -32767
            assert loaded[2] > 0
        finally:
            path.unlink(missing_ok=True)

    def test_save_wav_empty_audio(self):
        """Should handle empty audio array."""
        recorder = AudioRecorder()
        audio = np.array([], dtype=np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)

        try:
            recorder.save_wav(audio, path)
            assert path.exists()

            with wave.open(str(path), "rb") as wf:
                assert wf.getnframes() == 0
        finally:
            path.unlink(missing_ok=True)
