"""Tests for Transcriber class."""

import tempfile
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTranscriberInit:
    """Test Transcriber initialization."""

    @patch("dictation.WhisperModel")
    def test_loads_model_with_default_size(self, mock_whisper_model):
        """Should load base model by default."""
        from dictation import Transcriber

        Transcriber()

        mock_whisper_model.assert_called_once_with(
            "base", device="cpu", compute_type="int8"
        )

    @patch("dictation.WhisperModel")
    def test_loads_model_with_custom_size(self, mock_whisper_model):
        """Should load specified model size."""
        from dictation import Transcriber

        Transcriber(model_size="small")

        mock_whisper_model.assert_called_once_with(
            "small", device="cpu", compute_type="int8"
        )

    @patch("dictation.WhisperModel")
    def test_stores_language(self, mock_whisper_model):
        """Should store language setting."""
        from dictation import Transcriber

        transcriber = Transcriber(language="de")

        assert transcriber.language == "de"

    @patch("dictation.WhisperModel")
    def test_default_language_is_english(self, mock_whisper_model):
        """Should default to English language."""
        from dictation import Transcriber

        transcriber = Transcriber()

        assert transcriber.language == "en"

    @patch("dictation.WhisperModel")
    def test_stores_translate_flag(self, mock_whisper_model):
        """Should store translate flag."""
        from dictation import Transcriber

        transcriber = Transcriber(translate=True)

        assert transcriber.translate is True

    @patch("dictation.WhisperModel")
    def test_stores_multilingual_flag(self, mock_whisper_model):
        """Should store multilingual flag."""
        from dictation import Transcriber

        transcriber = Transcriber(multilingual=True)

        assert transcriber.multilingual is True

    @patch("dictation.WhisperModel")
    def test_stores_hotwords(self, mock_whisper_model):
        """Should store hotwords list."""
        from dictation import Transcriber

        transcriber = Transcriber(hotwords=["OpenAI", "Whisper"])

        assert transcriber.hotwords == ["OpenAI", "Whisper"]

    @patch("dictation.WhisperModel")
    def test_default_hotwords_empty(self, mock_whisper_model):
        """Should default to empty hotwords list."""
        from dictation import Transcriber

        transcriber = Transcriber()

        assert transcriber.hotwords == []


class TestTranscriberTranscribe:
    """Test Transcriber transcription functionality."""

    @patch("dictation.WhisperModel")
    def test_transcribe_calls_model(self, mock_whisper_model):
        """Should call model.transcribe with correct parameters."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(language="en")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            # Create minimal valid WAV
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)

            mock_model.transcribe.assert_called_once()
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["language"] == "en"
            assert call_kwargs["vad_filter"] is True
            assert call_kwargs["task"] == "transcribe"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_transcribe_returns_text(self, mock_whisper_model):
        """Should return transcribed text."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            result = transcriber.transcribe(path)
            assert result == "Hello world"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_transcribe_concatenates_segments(self, mock_whisper_model):
        """Should concatenate multiple segments."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_segment1 = MagicMock()
        mock_segment1.text = "Hello"
        mock_segment2 = MagicMock()
        mock_segment2.text = "world"
        mock_model.transcribe.return_value = (
            [mock_segment1, mock_segment2],
            MagicMock(),
        )
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            result = transcriber.transcribe(path)
            assert result == "Hello world"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_transcribe_strips_whitespace(self, mock_whisper_model):
        """Should strip whitespace from segments."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "  Hello world  "
        mock_model.transcribe.return_value = ([mock_segment], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            result = transcriber.transcribe(path)
            assert result == "Hello world"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_transcribe_empty_segments(self, mock_whisper_model):
        """Should handle empty segments list."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            result = transcriber.transcribe(path)
            assert result == ""
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_transcribe_uses_configured_language(self, mock_whisper_model):
        """Should use the configured language for transcription."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(language="de")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["language"] == "de"
        finally:
            path.unlink(missing_ok=True)


class TestTranscriberTranslation:
    """Test Transcriber translation functionality."""

    @patch("dictation.WhisperModel")
    def test_translate_sets_task(self, mock_whisper_model):
        """Should set task to translate when translate=True."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(translate=True)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["task"] == "translate"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_default_task_is_transcribe(self, mock_whisper_model):
        """Should default to transcribe task."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(translate=False)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["task"] == "transcribe"
        finally:
            path.unlink(missing_ok=True)


class TestTranscriberMultilingual:
    """Test Transcriber multilingual functionality."""

    @patch("dictation.WhisperModel")
    def test_multilingual_sets_language_none(self, mock_whisper_model):
        """Should set language to None when multilingual=True."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(multilingual=True, language="en")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["language"] is None
            assert call_kwargs["multilingual"] is True
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_non_multilingual_uses_language(self, mock_whisper_model):
        """Should use specified language when multilingual=False."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(multilingual=False, language="de")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["language"] == "de"
            assert call_kwargs["multilingual"] is False
        finally:
            path.unlink(missing_ok=True)


class TestTranscriberHotwords:
    """Test Transcriber hotwords functionality."""

    @patch("dictation.WhisperModel")
    def test_passes_hotwords_to_model(self, mock_whisper_model):
        """Should pass hotwords to the model."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(hotwords=["OpenAI", "Whisper", "GitHub"])

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["hotwords"] == "OpenAI Whisper GitHub"
        finally:
            path.unlink(missing_ok=True)

    @patch("dictation.WhisperModel")
    def test_empty_hotwords_passes_none(self, mock_whisper_model):
        """Should pass None when no hotwords specified."""
        from dictation import Transcriber

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        mock_whisper_model.return_value = mock_model

        transcriber = Transcriber(hotwords=[])

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = Path(f.name)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"\x00\x00" * 100)

        try:
            transcriber.transcribe(path)
            call_kwargs = mock_model.transcribe.call_args[1]
            assert call_kwargs["hotwords"] is None
        finally:
            path.unlink(missing_ok=True)
