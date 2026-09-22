"""Tests for cli.py's pure config-source-selection logic."""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfigFlagsPassed:
    """Tests for _config_flags_passed()."""

    def test_no_args_returns_false(self):
        from whisper_dictation.cli import _config_flags_passed

        assert _config_flags_passed(["dictation.py"]) is False

    def test_no_gui_alone_returns_false(self):
        from whisper_dictation.cli import _config_flags_passed

        assert _config_flags_passed(["dictation.py", "--no-gui"]) is False

    def test_model_flag_returns_true(self):
        from whisper_dictation.cli import _config_flags_passed

        assert _config_flags_passed(["dictation.py", "--model", "small"]) is True

    def test_no_gui_plus_another_flag_returns_true(self):
        from whisper_dictation.cli import _config_flags_passed

        assert (
            _config_flags_passed(["dictation.py", "--no-gui", "--recording-mode", "toggle"])
            is True
        )
