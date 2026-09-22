"""Transcription using Faster-Whisper."""

from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel


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
