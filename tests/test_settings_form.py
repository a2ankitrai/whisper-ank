"""Tests for build_config_from_fields()."""

from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def _base_fields(**overrides) -> dict:
    fields = {
        "model_size": "base",
        "language": "en",
        "grammar_engine": "none",
        "translate_to_english": False,
        "target_language": "none",
        "multilingual": False,
        "remove_fillers": True,
        "hotwords": "",
        "audio_feedback": True,
        "hotkey": "cmd+shift",
        "recording_mode": "push_to_talk",
        "replay_hotkey": "cmd+shift+v",
    }
    fields.update(overrides)
    return fields


class TestBuildConfigFromFields:
    """Tests for build_config_from_fields()."""

    def test_builds_matching_default_config(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(_base_fields(), base=DictationConfig())

        assert config == DictationConfig()

    def test_auto_language_and_none_target_language_become_none(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(
            _base_fields(language="auto", target_language="none"),
            base=DictationConfig(),
        )

        assert config.language is None
        assert config.target_language is None

    def test_grammar_engine_none_choice_becomes_none(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(
            _base_fields(grammar_engine="languagetool"), base=DictationConfig()
        )

        assert config.grammar_engine == "languagetool"

        config = build_config_from_fields(
            _base_fields(grammar_engine="none"), base=DictationConfig()
        )

        assert config.grammar_engine is None

    def test_hotwords_parsed_from_comma_separated_string(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(
            _base_fields(hotwords="OpenAI, Whisper ,GitHub"), base=DictationConfig()
        )

        assert config.hotwords == ["OpenAI", "Whisper", "GitHub"]

    def test_preserves_snippets_from_base_config(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        base = DictationConfig(snippets={"sig": "Best, Ankit"})

        config = build_config_from_fields(_base_fields(), base=base)

        assert config.snippets == {"sig": "Best, Ankit"}

    def test_parses_hotkey_and_replay_hotkey(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(
            _base_fields(hotkey="ctrl+alt", replay_hotkey="ctrl+alt+r"),
            base=DictationConfig(),
        )

        assert config.hotkey == {"ctrl", "alt"}
        assert config.replay_hotkey == (frozenset({"ctrl", "alt"}), "r")

    def test_invalid_hotkey_raises_value_error(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        with pytest.raises(ValueError):
            build_config_from_fields(
                _base_fields(hotkey="not+a+real+modifier"), base=DictationConfig()
            )

    def test_invalid_replay_hotkey_raises_value_error(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        with pytest.raises(ValueError):
            build_config_from_fields(
                _base_fields(replay_hotkey="cmd+shift"), base=DictationConfig()
            )
