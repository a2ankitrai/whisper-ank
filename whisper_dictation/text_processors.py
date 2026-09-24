"""Text processing pipeline: filler removal and snippet expansion."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod


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


class WordCorrector(TextProcessor):
    """Replaces commonly mis-transcribed words with their correct spelling.

    `corrections` maps what Whisper wrote ("kraxam") to what you meant
    ("Kragzam"). Matching is case-insensitive on whole words; the longest
    variants are tried first so multi-word entries beat their parts.
    """

    def __init__(self, corrections: dict[str, str]):
        variants = sorted(
            (k.strip() for k in corrections if k.strip()), key=len, reverse=True
        )
        self.corrections = {k.strip().lower(): v for k, v in corrections.items()}
        self._pattern = (
            re.compile(
                r"(?<!\w)(" + "|".join(re.escape(v) for v in variants) + r")(?!\w)",
                re.IGNORECASE,
            )
            if variants
            else None
        )

    def process(self, text: str) -> str:
        if not text or self._pattern is None:
            return text
        return self._pattern.sub(
            lambda m: self.corrections[m.group(1).lower()], text
        )
