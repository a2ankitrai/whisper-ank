"""Tests for TextTyper class."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTextTyperInit:
    """Test TextTyper initialization."""

    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_creates_event_source(self, mock_create_source):
        """Should create CGEvent source on init."""
        from whisper_dictation.text_typer import TextTyper

        mock_source = MagicMock()
        mock_create_source.return_value = mock_source

        typer = TextTyper()

        mock_create_source.assert_called_once()
        assert typer.source == mock_source

    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_checks_accessibility_permission(self, mock_create_source):
        """Should request accessibility permission on init."""
        with patch(
            "whisper_dictation.text_typer._ensure_accessibility_permission"
        ) as mock_ensure:
            from whisper_dictation.text_typer import TextTyper

            TextTyper()

            mock_ensure.assert_called_once()


class TestEnsureAccessibilityPermission:
    """Test the standalone accessibility permission check."""

    @patch("whisper_dictation.text_typer.AXIsProcessTrustedWithOptions")
    def test_prompts_with_expected_options(self, mock_check):
        """Should request the native OS prompt, not a silent check."""
        from whisper_dictation.text_typer import (
            _ensure_accessibility_permission,
            kAXTrustedCheckOptionPrompt,
        )

        mock_check.return_value = True

        _ensure_accessibility_permission()

        mock_check.assert_called_once_with({kAXTrustedCheckOptionPrompt: True})

    @patch("whisper_dictation.text_typer.AXIsProcessTrustedWithOptions")
    def test_warns_when_not_trusted(self, mock_check, capsys):
        """Should print guidance when permission is not granted."""
        from whisper_dictation.text_typer import _ensure_accessibility_permission

        mock_check.return_value = False

        _ensure_accessibility_permission()

        captured = capsys.readouterr()
        assert "Accessibility permission" in captured.out

    @patch("whisper_dictation.text_typer.AXIsProcessTrustedWithOptions")
    def test_silent_when_trusted(self, mock_check, capsys):
        """Should print nothing when permission is already granted."""
        from whisper_dictation.text_typer import _ensure_accessibility_permission

        mock_check.return_value = True

        _ensure_accessibility_permission()

        captured = capsys.readouterr()
        assert captured.out == ""


class TestTextTyperTypeText:
    """Test TextTyper text typing functionality."""

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_empty_string(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should do nothing for empty string."""
        from whisper_dictation.text_typer import TextTyper

        typer = TextTyper()
        typer.type_text("")

        mock_create_event.assert_not_called()
        mock_post.assert_not_called()

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_single_char(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should type single character."""
        from whisper_dictation.text_typer import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("a")

        # Should create key down and key up events
        assert mock_create_event.call_count == 2
        # Should set unicode string for both events
        assert mock_set_unicode.call_count == 2
        # Should post both events
        assert mock_post.call_count == 2

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_multiple_chars(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should type each character in sequence."""
        from whisper_dictation.text_typer import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("abc")

        # 3 chars × 2 events (down + up) = 6
        assert mock_create_event.call_count == 6
        # Should have delays between characters
        assert mock_sleep.call_count == 3

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_unicode(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should handle unicode characters."""
        from whisper_dictation.text_typer import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("日本語")

        # 3 unicode chars
        assert mock_create_event.call_count == 6

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_special_chars(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should handle special characters and punctuation."""
        from whisper_dictation.text_typer import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("Hello, world! How's it going?")

        # Should handle spaces, commas, exclamation, apostrophe, question mark
        expected_char_count = len("Hello, world! How's it going?")
        assert mock_create_event.call_count == expected_char_count * 2

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_newlines(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should handle newline characters."""
        from whisper_dictation.text_typer import TextTyper

        mock_event = MagicMock()
        mock_create_event.return_value = mock_event

        typer = TextTyper()
        typer.type_text("line1\nline2")

        # 11 chars including newline
        assert mock_create_event.call_count == 22

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_text_delay_between_chars(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
    ):
        """Should add delay between characters."""
        from whisper_dictation.text_typer import TextTyper

        typer = TextTyper()
        typer.type_text("ab")

        # Check sleep was called with expected delay
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.008)


class TestTextTyperRuntimePermissionChecks:
    """Test the per-call warnings that catch mid-session permission loss."""

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_no_warning_when_healthy(
        self, mock_source, mock_create_event, mock_set_unicode, mock_post, mock_sleep, capsys
    ):
        """Should print nothing when trusted and secure input is off."""
        from whisper_dictation.text_typer import TextTyper

        typer = TextTyper()
        typer.type_text("hi")

        assert capsys.readouterr().out == ""

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    @patch("whisper_dictation.text_typer.AXIsProcessTrusted")
    def test_warns_when_accessibility_revoked(
        self, mock_trusted, mock_source, mock_create_event, mock_set_unicode, mock_post, mock_sleep, capsys
    ):
        """Should warn when Accessibility trust is lost mid-session."""
        from whisper_dictation.text_typer import TextTyper

        mock_trusted.return_value = False

        typer = TextTyper()
        typer.type_text("hi")

        assert "Accessibility permission" in capsys.readouterr().out

    @patch("whisper_dictation.text_typer.time.sleep")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    @patch("whisper_dictation.text_typer._frontmost_app_name")
    @patch("whisper_dictation.text_typer._carbon")
    def test_warns_when_secure_input_enabled(
        self,
        mock_carbon,
        mock_frontmost,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_sleep,
        capsys,
    ):
        """Should warn, naming the frontmost app, when Secure Input is on."""
        from whisper_dictation.text_typer import TextTyper

        mock_carbon.IsSecureEventInputEnabled.return_value = True
        mock_frontmost.return_value = "1Password"

        typer = TextTyper()
        typer.type_text("hi")

        out = capsys.readouterr().out
        assert "Secure Keyboard Entry" in out
        assert "1Password" in out


class TestTextTyperTypeChar:
    """Test TextTyper single character typing."""

    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_char_creates_down_and_up_events(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
    ):
        """Should create both key down and key up events."""
        from whisper_dictation.text_typer import TextTyper

        mock_down = MagicMock()
        mock_up = MagicMock()
        mock_create_event.side_effect = [mock_down, mock_up]

        typer = TextTyper()
        typer._type_char("x")

        # Check events created with correct key down/up flags
        calls = mock_create_event.call_args_list
        assert calls[0][0][1] == 0  # keycode
        assert calls[0][0][2] is True  # key down
        assert calls[1][0][2] is False  # key up

    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_char_sets_unicode_on_both_events(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
    ):
        """Should set unicode string on both events."""
        from whisper_dictation.text_typer import TextTyper

        mock_down = MagicMock()
        mock_up = MagicMock()
        mock_create_event.side_effect = [mock_down, mock_up]

        typer = TextTyper()
        typer._type_char("é")

        # Unicode should be set on both events
        assert mock_set_unicode.call_count == 2
        mock_set_unicode.assert_any_call(mock_down, 1, "é")
        mock_set_unicode.assert_any_call(mock_up, 1, "é")

    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_char_posts_events_to_hid_tap(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
    ):
        """Should post events to HID event tap."""
        from whisper_dictation.text_typer import TextTyper, kCGHIDEventTap

        mock_down = MagicMock()
        mock_up = MagicMock()
        mock_create_event.side_effect = [mock_down, mock_up]

        typer = TextTyper()
        typer._type_char("z")

        # Should post to HID event tap
        assert mock_post.call_count == 2
        mock_post.assert_any_call(kCGHIDEventTap, mock_down)
        mock_post.assert_any_call(kCGHIDEventTap, mock_up)

    @patch("whisper_dictation.text_typer.CGEventSetFlags")
    @patch("whisper_dictation.text_typer.CGEventPost")
    @patch("whisper_dictation.text_typer.CGEventKeyboardSetUnicodeString")
    @patch("whisper_dictation.text_typer.CGEventCreateKeyboardEvent")
    @patch("whisper_dictation.text_typer.CGEventSourceCreate")
    def test_type_char_clears_modifier_flags(
        self,
        mock_source,
        mock_create_event,
        mock_set_unicode,
        mock_post,
        mock_set_flags,
    ):
        """Should clear inherited modifier flags.

        Typing happens on a background thread, so the user may already hold
        Cmd/Shift again; without clearing the flags the characters would be
        delivered as keyboard shortcuts.
        """
        from whisper_dictation.text_typer import TextTyper

        mock_down = MagicMock()
        mock_up = MagicMock()
        mock_create_event.side_effect = [mock_down, mock_up]

        typer = TextTyper()
        typer._type_char("z")

        mock_set_flags.assert_any_call(mock_down, 0)
        mock_set_flags.assert_any_call(mock_up, 0)
