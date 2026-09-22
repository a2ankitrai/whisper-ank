"""Tests for keyboard helper functions."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestKeyToChar:
    """Tests for key_to_char()."""

    def test_returns_lowercase_char_for_letter_key(self):
        """Should return the lowercase character for a plain letter key."""
        from whisper_dictation.keyboard import key_to_char
        from pynput.keyboard import KeyCode

        assert key_to_char(KeyCode.from_char("V")) == "v"
        assert key_to_char(KeyCode.from_char("v")) == "v"

    def test_returns_none_for_special_key(self):
        """Should return None for keys with no character (esc, arrows, etc.)."""
        from whisper_dictation.keyboard import key_to_char
        from pynput.keyboard import Key

        assert key_to_char(Key.esc) is None
        assert key_to_char(Key.space) is None

    def test_returns_none_for_modifier_key(self):
        """Should return None for modifier keys."""
        from whisper_dictation.keyboard import key_to_char
        from pynput.keyboard import Key

        assert key_to_char(Key.cmd) is None
        assert key_to_char(Key.shift) is None
