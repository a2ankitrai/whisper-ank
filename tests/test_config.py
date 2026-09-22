"""Tests for DictationConfig class."""

import pytest
import tempfile
from pathlib import Path
import sys
from unittest.mock import MagicMock
from argparse import Namespace

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDictationConfigDefaults:
    """Tests for DictationConfig default values."""

    def test_default_model_size(self):
        """Should default to base model."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.model_size == "base"

    def test_default_language(self):
        """Should default to English."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.language == "en"

    def test_default_grammar_engine(self):
        """Should default to no grammar engine."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.grammar_engine is None

    def test_default_translation_settings(self):
        """Should default to no translation."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.translate_to_english is False
        assert config.target_language is None

    def test_default_multilingual(self):
        """Should default to single language mode."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.multilingual is False

    def test_default_filler_removal(self):
        """Should default to filler removal enabled."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.remove_fillers is True

    def test_default_audio_feedback(self):
        """Should default to audio feedback enabled."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.audio_feedback is True

    def test_default_hotkey(self):
        """Should default to cmd+shift hotkey."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig()
        assert config.hotkey == {"cmd", "shift"}


class TestDictationConfigCustomValues:
    """Tests for DictationConfig with custom values."""

    def test_custom_model_size(self):
        """Should accept custom model size."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(model_size="large-v3")
        assert config.model_size == "large-v3"

    def test_custom_language(self):
        """Should accept custom language."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(language="de")
        assert config.language == "de"

    def test_null_language_for_multilingual(self):
        """Should accept None language for multilingual mode."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(language=None, multilingual=True)
        assert config.language is None
        assert config.multilingual is True

    def test_custom_grammar_engine(self):
        """Should accept grammar engine setting."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(grammar_engine="gramformer")
        assert config.grammar_engine == "gramformer"

    def test_custom_hotkey(self):
        """Should accept custom hotkey."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(hotkey={"ctrl", "alt"})
        assert config.hotkey == {"ctrl", "alt"}

    def test_custom_hotwords(self):
        """Should accept hotwords list."""
        from whisper_dictation.config import DictationConfig
        
        config = DictationConfig(hotwords=["OpenAI", "Whisper"])
        assert config.hotwords == ["OpenAI", "Whisper"]

    def test_custom_snippets(self):
        """Should accept snippets dict."""
        from whisper_dictation.config import DictationConfig
        
        snippets = {"sig": "Best regards"}
        config = DictationConfig(snippets=snippets)
        assert config.snippets == {"sig": "Best regards"}


class TestDictationConfigFromArgs:
    """Tests for DictationConfig.from_args()."""

    def test_parses_basic_args(self):
        """Should parse basic command line arguments."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="small",
            language="de",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.model_size == "small"
        assert config.language == "de"

    def test_parses_grammar_engine(self):
        """Should parse grammar engine argument."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar="gramformer",
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        assert config.grammar_engine == "gramformer"

    def test_parses_translation_settings(self):
        """Should parse translation arguments."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=True,
            target_language="nl",
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.translate_to_english is True
        assert config.target_language == "nl"

    def test_parses_multilingual_mode(self):
        """Should set language to None when multilingual is True."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=True,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.multilingual is True
        assert config.language is None

    def test_parses_hotwords(self):
        """Should parse comma-separated hotwords."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords="OpenAI,Whisper,GitHub",
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.hotwords == ["OpenAI", "Whisper", "GitHub"]

    def test_parses_custom_hotkey(self):
        """Should parse custom hotkey."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="ctrl+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.hotkey == {"ctrl", "shift"}

    def test_parses_keep_fillers(self):
        """Should disable filler removal when keep_fillers is True."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=True,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.remove_fillers is False

    def test_parses_no_audio_feedback(self):
        """Should disable audio feedback when flag is set."""
        from whisper_dictation.config import DictationConfig
        
        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=True,
            hotkey="cmd+shift",
        )
        
        config = DictationConfig.from_args(args)
        
        assert config.audio_feedback is False


class TestDictationConfigParseHotkey:
    """Tests for hotkey spec parsing and validation."""

    def test_parses_and_normalises(self):
        """Should lowercase, trim and de-duplicate modifiers."""
        from whisper_dictation.config import DictationConfig

        assert DictationConfig._parse_hotkey(" Cmd + SHIFT ") == {"cmd", "shift"}

    def test_rejects_unknown_modifier(self):
        """An unknown modifier can never match, so it must fail loudly."""
        from whisper_dictation.config import DictationConfig

        with pytest.raises(ValueError, match="banana"):
            DictationConfig._parse_hotkey("cmd+banana")

    def test_rejects_empty_hotkey(self):
        """An empty hotkey would make the app record permanently."""
        from whisper_dictation.config import DictationConfig

        with pytest.raises(ValueError):
            DictationConfig._parse_hotkey("+")


class TestDictationConfigRecordingMode:
    """Tests for recording_mode default/custom values and from_args."""

    def test_default_recording_mode(self):
        """Should default to push_to_talk."""
        from whisper_dictation.config import DictationConfig

        config = DictationConfig()
        assert config.recording_mode == "push_to_talk"

    def test_custom_recording_mode(self):
        """Should accept a custom recording mode."""
        from whisper_dictation.config import DictationConfig

        config = DictationConfig(recording_mode="toggle")
        assert config.recording_mode == "toggle"

    def test_parses_recording_mode_from_args(self):
        """Should parse recording_mode from CLI args."""
        from whisper_dictation.config import DictationConfig

        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
            recording_mode="toggle",
            replay_hotkey="cmd+shift+v",
        )

        config = DictationConfig.from_args(args)

        assert config.recording_mode == "toggle"


class TestDictationConfigReplayHotkey:
    """Tests for the replay hotkey default/custom values and parsing."""

    def test_default_replay_hotkey(self):
        """Should default to cmd+shift+v."""
        from whisper_dictation.config import DictationConfig

        config = DictationConfig()
        assert config.replay_hotkey == (frozenset({"cmd", "shift"}), "v")

    def test_parses_replay_hotkey_from_args(self):
        """Should parse a custom replay hotkey from CLI args."""
        from whisper_dictation.config import DictationConfig

        args = Namespace(
            model="base",
            language="en",
            grammar=None,
            translate=False,
            target_language=None,
            multilingual=False,
            keep_fillers=False,
            hotwords=None,
            snippets_file=None,
            no_audio_feedback=False,
            hotkey="cmd+shift",
            recording_mode="push_to_talk",
            replay_hotkey="ctrl+alt+r",
        )

        config = DictationConfig.from_args(args)

        assert config.replay_hotkey == (frozenset({"ctrl", "alt"}), "r")

    def test_parses_and_normalises(self):
        """Should lowercase and trim modifiers and the trailing key."""
        from whisper_dictation.config import DictationConfig

        assert DictationConfig._parse_replay_hotkey(" Cmd + SHIFT + V ") == (
            frozenset({"cmd", "shift"}),
            "v",
        )

    def test_rejects_unknown_modifier(self):
        """An unknown modifier can never match, so it must fail loudly."""
        from whisper_dictation.config import DictationConfig

        with pytest.raises(ValueError, match="banana"):
            DictationConfig._parse_replay_hotkey("banana+v")

    def test_rejects_missing_key(self):
        """A modifiers-only spec has no trailing key to trigger replay."""
        from whisper_dictation.config import DictationConfig

        with pytest.raises(ValueError):
            DictationConfig._parse_replay_hotkey("cmd+shift")

    def test_rejects_key_that_is_itself_a_modifier(self):
        """The trailing key must not be a modifier name."""
        from whisper_dictation.config import DictationConfig

        with pytest.raises(ValueError):
            DictationConfig._parse_replay_hotkey("cmd+shift+alt")


class TestDictationConfigLoadSnippets:
    """Tests for snippet file loading."""

    def test_loads_snippets_from_file(self):
        """Should load snippets from file."""
        from whisper_dictation.config import DictationConfig
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("signature=Best regards,\\nJohn\n")
            f.write("greeting=Hello there!\n")
            f.flush()
            path = f.name
        
        try:
            snippets = DictationConfig._load_snippets(path)
            
            assert "signature" in snippets
            assert "greeting" in snippets
            assert snippets["greeting"] == "Hello there!"
        finally:
            Path(path).unlink()

    def test_ignores_comments(self):
        """Should ignore lines starting with #."""
        from whisper_dictation.config import DictationConfig
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# This is a comment\n")
            f.write("greeting=Hello!\n")
            f.write("# Another comment\n")
            f.flush()
            path = f.name
        
        try:
            snippets = DictationConfig._load_snippets(path)
            
            assert len(snippets) == 1
            assert "greeting" in snippets
        finally:
            Path(path).unlink()

    def test_ignores_empty_lines(self):
        """Should ignore empty lines."""
        from whisper_dictation.config import DictationConfig
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("\n")
            f.write("greeting=Hello!\n")
            f.write("\n")
            f.flush()
            path = f.name
        
        try:
            snippets = DictationConfig._load_snippets(path)
            
            assert len(snippets) == 1
        finally:
            Path(path).unlink()

    def test_handles_missing_file(self):
        """Should handle missing file gracefully."""
        from whisper_dictation.config import DictationConfig
        
        snippets = DictationConfig._load_snippets("/nonexistent/path.txt")
        
        assert snippets == {}

    def test_handles_equals_in_value(self):
        """Should handle equals signs in snippet value."""
        from whisper_dictation.config import DictationConfig
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("equation=x = y + z\n")
            f.flush()
            path = f.name
        
        try:
            snippets = DictationConfig._load_snippets(path)
            
            assert snippets["equation"] == "x = y + z"
        finally:
            Path(path).unlink()
