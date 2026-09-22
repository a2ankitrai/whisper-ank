"""Pure validation/build logic for the settings window.

Kept free of any AppKit import so it's fully unit-testable; SettingsWindow
(the AppKit shell) reads its controls into a plain dict and delegates here.
"""

from __future__ import annotations

from .config import DictationConfig


def build_config_from_fields(fields: dict, base: DictationConfig) -> DictationConfig:
    """Build a validated DictationConfig from raw settings-window field values.

    `fields` keys: model_size, language ("auto" or an ISO 639-1 code),
    grammar_engine ("none" or an engine name), translate_to_english,
    target_language ("none" or an ISO 639-1 code), multilingual,
    remove_fillers, hotwords (comma-separated string), audio_feedback,
    hotkey (e.g. "cmd+shift"), recording_mode, replay_hotkey (e.g.
    "cmd+shift+v"). `base` supplies fields the settings window doesn't
    edit (snippets). Raises ValueError, with a message suitable for
    showing directly in the UI, on an invalid hotkey/replay-hotkey spec.
    """
    grammar_engine = fields["grammar_engine"]
    language = fields["language"]
    target_language = fields["target_language"]
    config = DictationConfig(
        model_size=fields["model_size"],
        language=None if language == "auto" else language,
        grammar_engine=None if grammar_engine == "none" else grammar_engine,
        translate_to_english=fields["translate_to_english"],
        target_language=None if target_language == "none" else target_language,
        multilingual=fields["multilingual"],
        remove_fillers=fields["remove_fillers"],
        hotwords=[h.strip() for h in fields["hotwords"].split(",") if h.strip()],
        snippets=dict(base.snippets),
        audio_feedback=fields["audio_feedback"],
        recording_mode=fields["recording_mode"],
    )
    config.hotkey = DictationConfig._parse_hotkey(fields["hotkey"])
    config.replay_hotkey = DictationConfig._parse_replay_hotkey(fields["replay_hotkey"])
    return config
