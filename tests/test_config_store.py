"""Tests for ConfigStore."""

from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfigStore:
    """Tests for ConfigStore.load()/save()."""

    def test_load_returns_none_when_file_missing(self, tmp_path):
        from whisper_dictation.config_store import ConfigStore

        store = ConfigStore(path=tmp_path / "does_not_exist.json")

        assert store.load() is None

    def test_save_then_load_round_trips(self, tmp_path):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.config_store import ConfigStore

        store = ConfigStore(path=tmp_path / "config.json")
        config = DictationConfig(model_size="small", recording_mode="toggle")

        store.save(config)
        restored = store.load()

        assert restored == config

    def test_save_creates_parent_directory(self, tmp_path):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.config_store import ConfigStore

        nested_path = tmp_path / "nested" / "dir" / "config.json"
        store = ConfigStore(path=nested_path)

        store.save(DictationConfig())

        assert nested_path.exists()

    def test_load_returns_none_on_corrupt_json(self, tmp_path, capsys):
        from whisper_dictation.config_store import ConfigStore

        path = tmp_path / "config.json"
        path.write_text("{not valid json")
        store = ConfigStore(path=path)

        assert store.load() is None

    def test_load_returns_none_on_invalid_schema(self, tmp_path):
        from whisper_dictation.config_store import ConfigStore

        path = tmp_path / "config.json"
        path.write_text('{"replay_hotkey": "not-a-dict"}')
        store = ConfigStore(path=path)

        assert store.load() is None
