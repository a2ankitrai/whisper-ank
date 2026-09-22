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
