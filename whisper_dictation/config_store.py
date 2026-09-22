"""Persisted GUI-managed configuration (JSON file on disk)."""

from __future__ import annotations

import json
from pathlib import Path

from .config import DictationConfig

DEFAULT_CONFIG_PATH = Path.home() / ".whisper_dictation" / "config.json"


class ConfigStore:
    """Reads/writes a DictationConfig to a JSON file on disk."""

    def __init__(self, path: Path = DEFAULT_CONFIG_PATH):
        self.path = path

    def load(self) -> DictationConfig | None:
        """Return the saved config, or None if missing/unreadable/invalid.

        A corrupt or missing config file must never prevent startup, so
        every failure mode here degrades to "use defaults" rather than
        raising.
        """
        try:
            raw = self.path.read_text()
        except FileNotFoundError:
            return None
        except OSError as e:
            print(f"⚠️  Could not read config file {self.path}: {e}")
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"⚠️  Could not parse config file {self.path}: {e}")
            return None

        try:
            return DictationConfig.from_json_dict(data)
        except (KeyError, TypeError, AttributeError) as e:
            print(f"⚠️  Invalid config file {self.path}: {e}")
            return None

    def save(self, config: DictationConfig) -> None:
        """Write config to disk, creating the parent directory if needed."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(config.to_json_dict(), indent=2))
