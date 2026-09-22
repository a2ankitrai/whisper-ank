"""Configuration for the dictation application."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from .keyboard import MODIFIER_FLAG_MASKS


@dataclass
class DictationConfig:
    """Configuration for the dictation application."""

    # Model settings
    model_size: str = "base"
    language: str | None = "en"

    # Grammar correction
    grammar_engine: str | None = None  # None, "languagetool", or "gramformer"

    # Translation settings
    translate_to_english: bool = False  # Use Whisper's translate task
    target_language: str | None = None  # For Argos translation (e.g., "nl" for Dutch)

    # Multilingual / code-mixing
    multilingual: bool = False

    # Text processing
    remove_fillers: bool = True
    hotwords: list[str] = field(default_factory=list)

    # Snippets (voice shortcuts)
    snippets: dict[str, str] = field(default_factory=dict)

    # Audio feedback
    audio_feedback: bool = True

    # Hotkey configuration
    hotkey: set[str] = field(default_factory=lambda: {"cmd", "shift"})

    # "push_to_talk" (hold to record) or "toggle" (press once to start/stop)
    recording_mode: str = "push_to_talk"

    # Hotkey that retypes the most recent transcription; (modifiers, key)
    replay_hotkey: tuple[frozenset[str], str] = field(
        default_factory=lambda: (frozenset({"cmd", "shift"}), "v")
    )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "DictationConfig":
        """Create config from command-line arguments."""
        config = cls(
            model_size=args.model,
            language=None if args.multilingual else args.language,
            grammar_engine=args.grammar,
            translate_to_english=args.translate,
            target_language=args.target_language,
            multilingual=args.multilingual,
            remove_fillers=not args.keep_fillers,
            hotwords=args.hotwords.split(",") if args.hotwords else [],
            audio_feedback=not args.no_audio_feedback,
            recording_mode=getattr(args, "recording_mode", "push_to_talk"),
        )

        # Parse hotkey
        if args.hotkey:
            config.hotkey = cls._parse_hotkey(args.hotkey)

        # Parse replay hotkey
        replay_hotkey_spec = getattr(args, "replay_hotkey", None)
        if replay_hotkey_spec:
            config.replay_hotkey = cls._parse_replay_hotkey(replay_hotkey_spec)

        # Load snippets from file if provided
        if args.snippets_file:
            config.snippets = cls._load_snippets(args.snippets_file)

        return config

    def to_json_dict(self) -> dict:
        """Serialize to a JSON-compatible dict (used by ConfigStore)."""
        modifiers, key = self.replay_hotkey
        return {
            "model_size": self.model_size,
            "language": self.language,
            "grammar_engine": self.grammar_engine,
            "translate_to_english": self.translate_to_english,
            "target_language": self.target_language,
            "multilingual": self.multilingual,
            "remove_fillers": self.remove_fillers,
            "hotwords": list(self.hotwords),
            "snippets": dict(self.snippets),
            "audio_feedback": self.audio_feedback,
            "hotkey": sorted(self.hotkey),
            "recording_mode": self.recording_mode,
            "replay_hotkey": {"modifiers": sorted(modifiers), "key": key},
        }

    @classmethod
    def from_json_dict(cls, data: dict) -> "DictationConfig":
        """Build a config from a dict produced by to_json_dict()."""
        defaults = cls()
        config = cls(
            model_size=data.get("model_size", defaults.model_size),
            language=data.get("language", defaults.language),
            grammar_engine=data.get("grammar_engine", defaults.grammar_engine),
            translate_to_english=data.get(
                "translate_to_english", defaults.translate_to_english
            ),
            target_language=data.get("target_language", defaults.target_language),
            multilingual=data.get("multilingual", defaults.multilingual),
            remove_fillers=data.get("remove_fillers", defaults.remove_fillers),
            hotwords=list(data.get("hotwords", defaults.hotwords)),
            snippets=dict(data.get("snippets", defaults.snippets)),
            audio_feedback=data.get("audio_feedback", defaults.audio_feedback),
            recording_mode=data.get("recording_mode", defaults.recording_mode),
        )
        if "hotkey" in data:
            config.hotkey = set(data["hotkey"])
        if "replay_hotkey" in data:
            replay = data["replay_hotkey"]
            config.replay_hotkey = (frozenset(replay["modifiers"]), replay["key"])
        return config

    @staticmethod
    def _parse_hotkey(spec: str) -> set[str]:
        """Parse a "cmd+shift" style hotkey spec into modifier names.

        Unknown modifiers are rejected loudly: silently accepting them would
        produce a hotkey that can never match, so the app would start up
        looking healthy but never record anything.
        """
        hotkey = {part.strip().lower() for part in spec.split("+") if part.strip()}
        if not hotkey:
            raise ValueError("Hotkey must contain at least one modifier")
        unknown = sorted(hotkey - set(MODIFIER_FLAG_MASKS))
        if unknown:
            supported = "+".join(sorted(MODIFIER_FLAG_MASKS))
            raise ValueError(
                f"Unsupported hotkey modifier(s): {', '.join(unknown)}. "
                f"Supported modifiers: {supported}"
            )
        return hotkey

    @staticmethod
    def _parse_replay_hotkey(spec: str) -> tuple[frozenset[str], str]:
        """Parse a "cmd+shift+v" style spec into (modifiers, trailing key).

        Unlike the record hotkey (modifiers only), replay needs a distinct
        trailing key so it can never fire as a side effect of the record
        combo itself.
        """
        parts = [part.strip().lower() for part in spec.split("+") if part.strip()]
        if len(parts) < 2:
            raise ValueError(
                "Replay hotkey must include at least one modifier and a key, "
                "e.g. 'cmd+shift+v'"
            )
        *modifier_parts, key = parts
        modifiers = frozenset(modifier_parts)
        unknown = sorted(modifiers - set(MODIFIER_FLAG_MASKS))
        if unknown:
            supported = "+".join(sorted(MODIFIER_FLAG_MASKS))
            raise ValueError(
                f"Unsupported replay hotkey modifier(s): {', '.join(unknown)}. "
                f"Supported modifiers: {supported}"
            )
        if key in MODIFIER_FLAG_MASKS:
            raise ValueError(
                f"Replay hotkey must end with a non-modifier key, got '{key}'"
            )
        return modifiers, key

    @staticmethod
    def _load_snippets(path: str) -> dict[str, str]:
        """Load snippets from a file (format: trigger=text per line)."""
        snippets = {}
        try:
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        trigger, text = line.split("=", 1)
                        snippets[trigger.strip().lower()] = text.strip()
        except FileNotFoundError:
            print(f"⚠️  Snippets file not found: {path}", file=sys.stderr)
        except (OSError, UnicodeDecodeError) as e:
            print(f"⚠️  Could not read snippets file {path}: {e}", file=sys.stderr)
        return snippets
