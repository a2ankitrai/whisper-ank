"""Tests for menu_bar_app pure helpers.

MenuBarApp itself needs a real macOS window server and is verified by
running the app, not by automated tests.
"""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFormatStatusTitle:
    """Tests for format_status_title()."""

    def test_idle_title(self):
        from whisper_dictation.menu_bar_app import format_status_title

        assert format_status_title(False) == "🎙️ Idle"

    def test_recording_title(self):
        from whisper_dictation.menu_bar_app import format_status_title

        assert format_status_title(True) == "🔴 Recording"
