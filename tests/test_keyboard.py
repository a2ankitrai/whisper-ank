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


class TestKeyMatches:
    def test_matches_by_keycode_when_option_changes_the_char(self):
        from pynput.keyboard import KeyCode
        from whisper_dictation.keyboard import key_matches

        assert key_matches(KeyCode(vk=2, char="\u2202"), "d")
        assert not key_matches(KeyCode(vk=3, char="\u0192"), "d")

    def test_falls_back_to_char(self):
        from pynput.keyboard import KeyCode
        from whisper_dictation.keyboard import key_matches

        assert key_matches(KeyCode.from_char("d"), "d")

    def test_special_key_does_not_match(self):
        from pynput.keyboard import Key
        from whisper_dictation.keyboard import key_matches

        assert not key_matches(Key.esc, "d")
