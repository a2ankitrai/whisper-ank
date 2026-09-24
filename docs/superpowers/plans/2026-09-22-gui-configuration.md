# GUI Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a macOS menu bar presence and a native settings window so the app's full configuration surface can be viewed and changed without CLI flags, with changes persisted to disk and applied to the running app live.

**Architecture:** `DictationApp.run()` is split into `start_background()` (starts the worker thread + pynput listener, returns) and the existing headless polling loop, so a new `rumps`-based `MenuBarApp` can start the same background threads and then take the main thread's Cocoa run loop instead. A native AppKit `SettingsWindow` edits the full `DictationConfig`, validated through a pure `build_config_from_fields()` helper, persisted via a new `ConfigStore` (JSON file), and applied live through a new `DictationApp.apply_config()` that rebuilds the transcriber/text-processing pipeline atomically.

**Tech Stack:** Python, `rumps` (new dependency, thin wrapper over the already-installed `pyobjc-framework-Cocoa`), `AppKit`/`objc` (PyObjC, already installed), `pytest` + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-22-gui-configuration-design.md`

## Global Constraints

- macOS only — no cross-platform GUI abstraction; this matches the rest of the app (pyobjc, CGEventTap).
- No second GUI toolkit alongside AppKit/rumps (e.g. no Tkinter) — one native event loop.
- Config file lives at `~/.whisper_dictation/config.json`.
- Running with **no CLI flags** loads the saved config file if present and defaults to GUI mode.
- Running with **any CLI flag other than `--no-gui`** uses classic argparse-only config for that run (file is ignored, nothing persisted).
- `--no-gui` forces headless console mode regardless of the above.
- `apply_config()` must be atomic: if rebuilding the transcriber/grammar corrector raises, none of the running app's state changes and the previous instances stay in place.
- Snippets are not edited through the GUI (out of scope per the spec) — the settings window preserves whatever `snippets` the app already has.

---

### Task 1: Config JSON serialization

**Files:**
- Modify: `whisper_dictation/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `DictationConfig.to_json_dict(self) -> dict`, `DictationConfig.from_json_dict(data: dict) -> DictationConfig` (classmethod). Used by Task 2's `ConfigStore`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py` (new test class, placed before `TestDictationConfigLoadSnippets`):

```python
class TestDictationConfigJsonRoundTrip:
    """Tests for to_json_dict()/from_json_dict()."""

    def test_default_config_round_trips(self):
        from whisper_dictation.config import DictationConfig

        config = DictationConfig()
        restored = DictationConfig.from_json_dict(config.to_json_dict())

        assert restored == config

    def test_custom_config_round_trips(self):
        from whisper_dictation.config import DictationConfig

        config = DictationConfig(
            model_size="small",
            language="nl",
            grammar_engine="languagetool",
            translate_to_english=True,
            target_language="de",
            multilingual=True,
            remove_fillers=False,
            hotwords=["OpenAI", "Whisper"],
            snippets={"sig": "Best, Ankit"},
            audio_feedback=False,
            hotkey={"ctrl", "alt"},
            recording_mode="toggle",
            replay_hotkey=(frozenset({"ctrl"}), "r"),
        )

        restored = DictationConfig.from_json_dict(config.to_json_dict())

        assert restored == config

    def test_to_json_dict_is_json_serializable(self):
        import json

        from whisper_dictation.config import DictationConfig

        config = DictationConfig()
        # Must not raise: sets/frozensets aren't directly JSON-serializable,
        # to_json_dict() must have already converted them.
        json.dumps(config.to_json_dict())

    def test_from_json_dict_fills_in_missing_keys_with_defaults(self):
        from whisper_dictation.config import DictationConfig

        restored = DictationConfig.from_json_dict({"model_size": "tiny"})

        assert restored.model_size == "tiny"
        assert restored.hotkey == {"cmd", "shift"}
        assert restored.replay_hotkey == (frozenset({"cmd", "shift"}), "v")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_config.py::TestDictationConfigJsonRoundTrip -v`
Expected: FAIL with `AttributeError: 'DictationConfig' object has no attribute 'to_json_dict'`

- [ ] **Step 3: Implement `to_json_dict`/`from_json_dict`**

In `whisper_dictation/config.py`, add these methods to `DictationConfig` (after `from_args`, before `_parse_hotkey`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/test_config.py -v`
Expected: PASS (all tests, including the new ones)

- [ ] **Step 5: Commit**

```bash
git add whisper_dictation/config.py tests/test_config.py
git commit -m "feat: add JSON serialization to DictationConfig

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: ConfigStore (persisted GUI config)

**Files:**
- Create: `whisper_dictation/config_store.py`
- Test: `tests/test_config_store.py`

**Interfaces:**
- Consumes: `DictationConfig.to_json_dict()`, `DictationConfig.from_json_dict()` (Task 1).
- Produces: `ConfigStore(path: Path = DEFAULT_CONFIG_PATH)`, `ConfigStore.load() -> DictationConfig | None`, `ConfigStore.save(config: DictationConfig) -> None`, `DEFAULT_CONFIG_PATH: Path`. Used by Task 7 (SettingsWindow) and Task 8 (cli.py).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_config_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'whisper_dictation.config_store'`

- [ ] **Step 3: Implement ConfigStore**

Create `whisper_dictation/config_store.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/test_config_store.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add whisper_dictation/config_store.py tests/test_config_store.py
git commit -m "feat: add ConfigStore for persisting GUI config to disk

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: DictationApp pipeline refactor + apply_config()

**Files:**
- Modify: `whisper_dictation/dictation_app.py:30-116` (`__init__`)
- Test: `tests/test_dictation_app.py`

**Interfaces:**
- Consumes: `DictationConfig` (existing).
- Produces: `DictationApp._build_pipeline(config: DictationConfig) -> None` (sets `self.transcriber`, `self.processors`, `self.grammar_corrector`, `self.translator`), `DictationApp.apply_config(new_config: DictationConfig) -> None`. Used by Task 6 (MenuBarApp quick toggles) and Task 7 (SettingsWindow Save).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dictation_app.py` (new test class, placed before `TestDictationAppThreadSafety`):

```python
class TestDictationAppApplyConfig:
    """Tests for apply_config() (live settings updates)."""

    def _make_app(self, **config_kwargs):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp

        with patch("whisper_dictation.dictation_app.AudioFeedback"), \
             patch("whisper_dictation.dictation_app.TextTyper"), \
             patch("whisper_dictation.dictation_app.Transcriber"), \
             patch("whisper_dictation.dictation_app.AudioRecorder"):
            return DictationApp(config=DictationConfig(**config_kwargs))

    def test_updates_hotkey_recording_mode_and_replay_hotkey(self):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        new_config = DictationConfig(
            hotkey={"ctrl", "alt"},
            recording_mode="toggle",
            replay_hotkey=(frozenset({"ctrl"}), "r"),
        )

        with patch("whisper_dictation.dictation_app.Transcriber"):
            app.apply_config(new_config)

        assert app.hotkey == {"ctrl", "alt"}
        assert app.recording_mode == "toggle"
        assert app.replay_hotkey == (frozenset({"ctrl"}), "r")
        assert app.config == new_config

    def test_updates_audio_feedback_enabled_flag(self):
        from whisper_dictation.config import DictationConfig

        app = self._make_app(audio_feedback=True)
        new_config = DictationConfig(audio_feedback=False)

        with patch("whisper_dictation.dictation_app.Transcriber"):
            app.apply_config(new_config)

        assert app.audio_feedback.enabled is False

    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_rebuilds_transcriber_with_new_model_settings(self, mock_transcriber_cls):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        new_config = DictationConfig(model_size="large-v3", language="nl")

        app.apply_config(new_config)

        call_kwargs = mock_transcriber_cls.call_args[1]
        assert call_kwargs["model_size"] == "large-v3"
        assert call_kwargs["language"] == "nl"

    @patch("whisper_dictation.dictation_app.create_grammar_corrector")
    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_rebuilds_grammar_corrector(self, mock_transcriber_cls, mock_create_corrector):
        from whisper_dictation.config import DictationConfig

        mock_corrector = MagicMock()
        mock_create_corrector.return_value = mock_corrector
        app = self._make_app()
        new_config = DictationConfig(grammar_engine="languagetool")

        app.apply_config(new_config)

        assert app.grammar_corrector is mock_corrector
        assert mock_corrector in app.processors

    @patch("whisper_dictation.dictation_app.Transcriber")
    def test_invalid_new_config_leaves_previous_state_untouched(self, mock_transcriber_cls):
        from whisper_dictation.config import DictationConfig

        app = self._make_app()
        original_transcriber = app.transcriber
        mock_transcriber_cls.side_effect = ValueError("boom")
        new_config = DictationConfig(model_size="not-a-real-model")

        with pytest.raises(ValueError):
            app.apply_config(new_config)

        assert app.transcriber is original_transcriber
        assert app.hotkey == {"cmd", "shift"}  # unchanged, not the new_config's
        assert app.config.model_size == "base"  # unchanged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_dictation_app.py::TestDictationAppApplyConfig -v`
Expected: FAIL with `AttributeError: 'DictationApp' object has no attribute 'apply_config'`

- [ ] **Step 3: Extract `_build_pipeline` and add `apply_config`**

In `whisper_dictation/dictation_app.py`, replace this block in `__init__` (currently lines 47-88):

```python
        # Core components
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber(
            model_size=config.model_size,
            language=config.language,
            translate=config.translate_to_english,
            multilingual=config.multilingual,
            hotwords=config.hotwords,
        )
        self.typer = TextTyper()
        self.audio_feedback = AudioFeedback(enabled=config.audio_feedback)

        # Build text processing pipeline
        self.processors: list[TextProcessor] = []

        # 1. Filler removal (first, to clean up raw transcription)
        if config.remove_fillers:
            self.processors.append(FillerRemover())

        # 2. Snippet expansion
        if config.snippets:
            self.processors.append(SnippetExpander(config.snippets))

        # 3. Grammar correction
        self.grammar_corrector = create_grammar_corrector(
            config.grammar_engine,
            config.language or "en"
        )
        if self.grammar_corrector:
            self.processors.append(self.grammar_corrector)

        # 4. Translation (English → target language)
        self.translator: Translator | None = None
        if config.target_language:
            self.translator = ArgosTranslator(
                source_lang="en",
                target_lang=config.target_language
            )
            self.processors.append(self.translator)

        # Legacy compatibility
        self.enable_grammar = config.grammar_engine is not None
```

with:

```python
        # Core components
        self.recorder = AudioRecorder()
        self.typer = TextTyper()
        self.audio_feedback = AudioFeedback(enabled=config.audio_feedback)
        self._build_pipeline(config)

        # Legacy compatibility
        self.enable_grammar = config.grammar_engine is not None
```

Then add these two methods right after `__init__` (before `# -- Worker --` section):

```python
    def _build_pipeline(self, config: DictationConfig) -> None:
        """(Re)build the transcriber and text-processing pipeline from config.

        Builds everything into local variables first and only assigns to
        `self` once all construction succeeds, so a failure (e.g. an
        invalid model size) never leaves the app with a half-updated
        pipeline — see apply_config().
        """
        transcriber = Transcriber(
            model_size=config.model_size,
            language=config.language,
            translate=config.translate_to_english,
            multilingual=config.multilingual,
            hotwords=config.hotwords,
        )

        processors: list[TextProcessor] = []

        # 1. Filler removal (first, to clean up raw transcription)
        if config.remove_fillers:
            processors.append(FillerRemover())

        # 2. Snippet expansion
        if config.snippets:
            processors.append(SnippetExpander(config.snippets))

        # 3. Grammar correction
        grammar_corrector = create_grammar_corrector(
            config.grammar_engine,
            config.language or "en"
        )
        if grammar_corrector:
            processors.append(grammar_corrector)

        # 4. Translation (English → target language)
        translator: Translator | None = None
        if config.target_language:
            translator = ArgosTranslator(
                source_lang="en",
                target_lang=config.target_language
            )
            processors.append(translator)

        self.transcriber = transcriber
        self.processors = processors
        self.grammar_corrector = grammar_corrector
        self.translator = translator

    def apply_config(self, new_config: DictationConfig) -> None:
        """Apply a changed config to the running app without a restart.

        Rebuilds the (possibly slow, possibly failing) pipeline first;
        only if that succeeds do the cheap live attributes and self.config
        get updated, so a bad config never leaves the app half-changed.
        """
        self._build_pipeline(new_config)

        with self.lock:
            self.hotkey = new_config.hotkey
            self.recording_mode = new_config.recording_mode
            self.replay_hotkey = new_config.replay_hotkey
            self.audio_feedback.enabled = new_config.audio_feedback

        self.config = new_config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/test_dictation_app.py -v`
Expected: PASS (all tests, including the 5 new ones — this also re-verifies `__init__` behavior is unchanged)

- [ ] **Step 5: Commit**

```bash
git add whisper_dictation/dictation_app.py tests/test_dictation_app.py
git commit -m "feat: add DictationApp.apply_config() for live settings updates

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: Split DictationApp.run() into start_background()/poll_health()

**Files:**
- Modify: `whisper_dictation/dictation_app.py:90-116` (state block), `whisper_dictation/dictation_app.py:405-549` (`run()`)
- Test: `tests/test_dictation_app.py`

**Interfaces:**
- Produces: `DictationApp.start_background() -> None`, `DictationApp.poll_health() -> None`, `DictationApp._print_banner() -> None`, instance attrs `self.listener`, `self.listener_started_at`, `self._last_stall_warning`. `run()` keeps its existing signature and headless behavior. Used by Task 6 (`MenuBarApp.run()` calls `start_background()`; its timer calls `poll_health()`).

- [ ] **Step 1: Add new state attributes**

In `whisper_dictation/dictation_app.py`, in `__init__`, right after this existing line:

```python
        self.command_started_at: tuple[float, str] | None = None
```

add:

```python
        self.listener = None
        self.listener_started_at: float | None = None
        self._last_stall_warning: float | None = None
```

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_dictation_app.py` (new test class, placed before `TestDictationAppThreadSafety`):

```python
class TestDictationAppBackgroundLifecycle:
    """Tests for start_background()/poll_health() (GUI/headless shared plumbing)."""

    def _make_app(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.dictation_app import DictationApp

        with patch("whisper_dictation.dictation_app.AudioFeedback"), \
             patch("whisper_dictation.dictation_app.TextTyper"), \
             patch("whisper_dictation.dictation_app.Transcriber"), \
             patch("whisper_dictation.dictation_app.AudioRecorder"):
            return DictationApp(config=DictationConfig())

    @patch("whisper_dictation.dictation_app._resilient_listener_class")
    def test_start_background_starts_worker_and_listener(self, mock_listener_cls):
        app = self._make_app()
        fake_listener = MagicMock()
        fake_listener.running = True
        mock_listener_cls.return_value = MagicMock(return_value=fake_listener)

        app.start_background()
        try:
            assert app.worker.is_alive()
            assert app.listener is fake_listener
            fake_listener.start.assert_called_once()
            fake_listener.wait.assert_called_once()
        finally:
            app.running = False
            app.worker.join(timeout=2)

    @patch("whisper_dictation.dictation_app.live_modifiers", return_value=set())
    @patch("whisper_dictation.dictation_app._resilient_listener_class")
    def test_poll_health_rebuilds_dead_listener(self, mock_listener_cls, mock_live_modifiers):
        app = self._make_app()
        dead_listener = MagicMock()
        dead_listener.running = False
        new_listener = MagicMock()
        new_listener.running = True
        mock_listener_cls.return_value = MagicMock(side_effect=[new_listener])
        app.listener = dead_listener
        app.listener_started_at = time.monotonic()

        app.poll_health()

        dead_listener.stop.assert_called_once()
        assert app.listener is new_listener
        new_listener.start.assert_called_once()

    @patch("whisper_dictation.dictation_app.live_modifiers", return_value=set())
    def test_poll_health_warns_on_stalled_command(self, mock_live_modifiers, capsys):
        app = self._make_app()
        alive_listener = MagicMock()
        alive_listener.running = True
        alive_listener.ensure_tap_enabled.return_value = False
        app.listener = alive_listener
        app.listener_started_at = time.monotonic()
        app.command_started_at = (time.monotonic() - 6, "start")

        app.poll_health()

        captured = capsys.readouterr()
        assert "stuck for" in captured.err
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_dictation_app.py::TestDictationAppBackgroundLifecycle -v`
Expected: FAIL with `AttributeError: 'DictationApp' object has no attribute 'start_background'`

- [ ] **Step 4: Replace `run()` with the split implementation**

In `whisper_dictation/dictation_app.py`, replace the entire existing `run()` method (from `def run(self):` through the final `self.recorder.close()`) with:

```python
    def _print_banner(self) -> None:
        """Print the startup banner (hotkeys, active features)."""
        hotkey_display = "+".join(k.capitalize() for k in sorted(self.hotkey))
        replay_modifiers, replay_key = self.replay_hotkey
        replay_display = "+".join(
            k.capitalize() for k in sorted(replay_modifiers)
        ) + f"+{replay_key.upper()}"

        print("\n" + "=" * 60)
        print("🎙️  WHISPER DICTATION")
        print("=" * 60)
        if self.recording_mode == "toggle":
            print(f"Press {hotkey_display} to start recording, press again to stop")
        else:
            print(f"Hold {hotkey_display} to record")
            print("Release to transcribe and type")
        print(f"Press {replay_display} to retype the last transcription")
        print("Press Escape to quit")
        print("-" * 60)

        features = []
        if self.config.multilingual:
            features.append("Multilingual (code-mixing)")
        else:
            features.append(f"Language: {self.config.language or 'auto'}")

        if self.config.translate_to_english:
            features.append("Translation: → English")

        if self.config.target_language:
            features.append(f"Translation: English → {self.config.target_language}")

        if self.config.grammar_engine:
            features.append(f"Grammar: {self.config.grammar_engine}")

        if self.config.remove_fillers:
            features.append("Filler removal: ON")

        if self.config.hotwords:
            features.append(f"Hotwords: {len(self.config.hotwords)}")

        if self.config.snippets:
            features.append(f"Snippets: {len(self.config.snippets)}")

        if self.config.audio_feedback:
            features.append("Audio feedback: ON")

        for feature in features:
            print(f"  • {feature}")

        print("=" * 60)
        print("\n🎯 Ready...\n")

    def start_background(self) -> None:
        """Start the worker thread and keyboard listener; returns immediately.

        Shared by headless run() and GUI mode: MenuBarApp calls this, then
        takes the main thread's Cocoa run loop itself instead of running
        the polling loop below.
        """
        faulthandler.enable()
        try:
            faulthandler.register(signal.SIGUSR1, all_threads=True, chain=False)
        except Exception:
            pass

        try:
            signal.signal(signal.SIGHUP, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except ValueError:
            # Signals can only be registered from the main thread
            pass

        self._print_banner()

        listener_cls = _resilient_listener_class()
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()

        self.listener = listener_cls(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self.listener.start()
        self.listener_started_at = time.monotonic()
        self.listener.wait()

    def poll_health(self) -> None:
        """One iteration of periodic health-check work.

        Shared by run()'s headless polling loop and MenuBarApp's
        rumps.Timer — exactly one of those two drives it in a given run,
        they are mutually exclusive main-thread owners.
        """
        if not self.listener.running:
            # The listener thread died (permissions revoked, tap creation
            # failed); rebuild it instead of going silent.
            print("⚠️  Keyboard listener stopped, restarting it...")
            try:
                self.listener.stop()
            except Exception:
                pass
            listener_cls = _resilient_listener_class()
            self.listener = listener_cls(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self.listener.start()
            self.listener_started_at = time.monotonic()
            self.last_event_at = None
            self._no_events_warned_at = None
            self.listener.wait()
            self._resync_modifiers()
            return

        if self.listener.ensure_tap_enabled():
            print("⚠️  Event tap was disabled by macOS, re-enabled it")

        self._resync_modifiers()
        self._check_event_flow(self.listener_started_at)

        started = self.command_started_at
        if started:
            now = time.monotonic()
            if now - started[0] > 5:
                if (
                    self._last_stall_warning is None
                    or now - self._last_stall_warning > 10
                ):
                    self._last_stall_warning = now
                    print(
                        f"⚠️  Audio command '{started[1]}' has been "
                        f"stuck for {now - started[0]:.0f}s "
                        f"(send SIGUSR1 to this PID for a stack dump)",
                        file=sys.stderr,
                    )

    def run(self) -> None:
        """Run headless (no GUI): start background threads, then poll forever."""
        self.start_background()
        try:
            last_health_check = 0.0
            while self.running:
                time.sleep(0.1)
                now = time.monotonic()
                if now - last_health_check >= 0.5:
                    last_health_check = now
                    self.poll_health()
        except Exception as e:
            print(f"\n❌ Listener error: {e}", file=sys.stderr)
            print(
                "   This is often caused by missing Accessibility/Input "
                "Monitoring permission for the Python process.",
                file=sys.stderr,
            )
        finally:
            self.running = False
            try:
                self.listener.stop()
            except Exception:
                pass
            if self.worker:
                self.worker.join(timeout=2)
            self.recorder.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/ -v`
Expected: PASS (full suite — this refactor must not break any existing test)

- [ ] **Step 6: Commit**

```bash
git add whisper_dictation/dictation_app.py tests/test_dictation_app.py
git commit -m "refactor: split DictationApp.run() into start_background()/poll_health()

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: settings_form.py (pure validation/build logic)

**Files:**
- Create: `whisper_dictation/settings_form.py`
- Test: `tests/test_settings_form.py`

**Interfaces:**
- Consumes: `DictationConfig` (existing), `DictationConfig._parse_hotkey`, `DictationConfig._parse_replay_hotkey` (existing).
- Produces: `build_config_from_fields(fields: dict, base: DictationConfig) -> DictationConfig`. Used by Task 7 (`SettingsWindow.save_`).

This is deliberately a plain module with zero AppKit imports so it's fully unit-testable — the AppKit shell in Task 7 is a thin, untested layer on top of it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings_form.py`:

```python
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
        "target_language": "",
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

    def test_empty_language_and_target_language_become_none(self):
        from whisper_dictation.config import DictationConfig
        from whisper_dictation.settings_form import build_config_from_fields

        config = build_config_from_fields(
            _base_fields(language="  ", target_language="  "), base=DictationConfig()
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_settings_form.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'whisper_dictation.settings_form'`

- [ ] **Step 3: Implement build_config_from_fields**

Create `whisper_dictation/settings_form.py`:

```python
"""Pure validation/build logic for the settings window.

Kept free of any AppKit import so it's fully unit-testable; SettingsWindow
(the AppKit shell) reads its controls into a plain dict and delegates here.
"""

from __future__ import annotations

from .config import DictationConfig


def build_config_from_fields(fields: dict, base: DictationConfig) -> DictationConfig:
    """Build a validated DictationConfig from raw settings-window field values.

    `fields` keys: model_size, language, grammar_engine ("none" or an
    engine name), translate_to_english, target_language, multilingual,
    remove_fillers, hotwords (comma-separated string), audio_feedback,
    hotkey (e.g. "cmd+shift"), recording_mode, replay_hotkey (e.g.
    "cmd+shift+v"). `base` supplies fields the settings window doesn't
    edit (snippets). Raises ValueError, with a message suitable for
    showing directly in the UI, on an invalid hotkey/replay-hotkey spec.
    """
    grammar_engine = fields["grammar_engine"]
    config = DictationConfig(
        model_size=fields["model_size"],
        language=fields["language"].strip() or None,
        grammar_engine=None if grammar_engine == "none" else grammar_engine,
        translate_to_english=fields["translate_to_english"],
        target_language=fields["target_language"].strip() or None,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/test_settings_form.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add whisper_dictation/settings_form.py tests/test_settings_form.py
git commit -m "feat: add pure settings-form validation/build logic

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: rumps dependency + MenuBarApp

**Files:**
- Modify: `requirements.txt`
- Create: `whisper_dictation/menu_bar_app.py`
- Test: `tests/test_menu_bar_app.py`

**Interfaces:**
- Consumes: `DictationApp.start_background()`, `DictationApp.poll_health()`, `DictationApp.apply_config()` (Tasks 3-4), `DictationApp.is_recording`, `DictationApp.running`, `DictationApp.config` (existing).
- Produces: `format_status_title(is_recording: bool) -> str`, `MenuBarApp(rumps.App)` with `__init__(dictation_app: DictationApp)` and `run(**kwargs)`. Used by Task 8 (cli.py).

**Note on testability:** `MenuBarApp` itself needs a real macOS window server/NSApplication and is not unit-tested here — only the pure `format_status_title()` helper is. Verify `MenuBarApp` by running the app (see Task 8's manual verification step).

- [ ] **Step 1: Add the `rumps` dependency**

In `requirements.txt`, add this line after the `pyobjc-framework-Cocoa` line:

```
rumps
```

Install it:

Run: `./venv/bin/pip install rumps`
Expected: `Successfully installed rumps-<version>`

- [ ] **Step 2: Write the failing test for the pure helper**

Create `tests/test_menu_bar_app.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/bin/python3 -m pytest tests/test_menu_bar_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'whisper_dictation.menu_bar_app'`

- [ ] **Step 4: Implement MenuBarApp**

Create `whisper_dictation/menu_bar_app.py`:

```python
"""Menu bar app: hosts the main thread's run loop and quick-access controls."""

from __future__ import annotations

import dataclasses

import rumps

from .dictation_app import DictationApp

POLL_INTERVAL = 0.5


def format_status_title(is_recording: bool) -> str:
    """Menu bar title reflecting whether dictation is currently recording."""
    return "🔴 Recording" if is_recording else "🎙️ Idle"


class MenuBarApp(rumps.App):
    """macOS menu bar presence for a running DictationApp."""

    def __init__(self, dictation_app: DictationApp):
        super().__init__(format_status_title(False), quit_button=None)
        self.dictation_app = dictation_app
        self._settings_window = None

        self.recording_mode_item = rumps.MenuItem(
            "Toggle Mode: Push-to-talk", callback=self._toggle_recording_mode
        )
        self.audio_feedback_item = rumps.MenuItem(
            "Audio Feedback", callback=self._toggle_audio_feedback
        )
        self.audio_feedback_item.state = dictation_app.config.audio_feedback
        self._sync_recording_mode_label()

        self.menu = [
            self.recording_mode_item,
            self.audio_feedback_item,
            rumps.MenuItem("Settings…", callback=self._open_settings),
            None,
            rumps.MenuItem("Quit", callback=self._quit),
        ]

    def run(self, **kwargs):
        """Start DictationApp's background threads, then take the main thread."""
        self.dictation_app.start_background()
        rumps.Timer(self._poll, POLL_INTERVAL).start()
        super().run(**kwargs)

    def _sync_recording_mode_label(self) -> None:
        mode = self.dictation_app.config.recording_mode
        label = "Push-to-talk" if mode == "push_to_talk" else "Toggle"
        self.recording_mode_item.title = f"Recording Mode: {label} (click to switch)"

    def _poll(self, _timer):
        self.dictation_app.poll_health()
        self.title = format_status_title(self.dictation_app.is_recording)
        if not self.dictation_app.running:
            rumps.quit_application()

    def _toggle_recording_mode(self, _sender):
        current = self.dictation_app.config
        new_mode = "toggle" if current.recording_mode == "push_to_talk" else "push_to_talk"
        self.dictation_app.apply_config(dataclasses.replace(current, recording_mode=new_mode))
        self._sync_recording_mode_label()

    def _toggle_audio_feedback(self, sender):
        current = self.dictation_app.config
        new_config = dataclasses.replace(current, audio_feedback=not current.audio_feedback)
        self.dictation_app.apply_config(new_config)
        sender.state = new_config.audio_feedback

    def _open_settings(self, _sender):
        from .settings_window import open_settings_window

        # Keep a reference so ARC/PyObjC doesn't release the window early.
        self._settings_window = open_settings_window(self.dictation_app)

    def _quit(self, _sender):
        self.dictation_app.running = False
        rumps.quit_application()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `./venv/bin/python3 -m pytest tests/test_menu_bar_app.py -v`
Expected: PASS (both tests)

- [ ] **Step 6: Run the full test suite**

Run: `./venv/bin/python3 -m pytest tests/ -v`
Expected: PASS (importing `menu_bar_app` pulls in `rumps` and transitively `AppKit` — this confirms that import chain works in this environment)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt whisper_dictation/menu_bar_app.py tests/test_menu_bar_app.py
git commit -m "feat: add MenuBarApp (rumps-based menu bar presence)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 7: SettingsWindow (native AppKit form)

**Files:**
- Create: `whisper_dictation/settings_window.py`

**Interfaces:**
- Consumes: `build_config_from_fields()` (Task 5), `ConfigStore` (Task 2), `DictationApp.apply_config()` (Task 3), `DictationApp.config` (existing).
- Produces: `open_settings_window(dictation_app: DictationApp) -> SettingsWindow`. Used by Task 6's `MenuBarApp._open_settings` (already written to call it).

**Note on testability:** this is a native AppKit window and is not unit-tested — its only tested dependency is `build_config_from_fields()` (Task 5). Verify by running the app: open Settings, confirm every field shows the current config, change a few values, click Save, confirm the change takes effect (e.g. switch recording mode and try it) and persists after restarting the app.

- [ ] **Step 1: Implement SettingsWindow**

Create `whisper_dictation/settings_window.py`:

```python
"""Native macOS settings window (PyObjC/AppKit) for GUI-driven configuration.

Built directly on AppKit rather than a second GUI toolkit (e.g. Tkinter) so
there's exactly one native event loop, matching the rumps-based MenuBarApp
that owns it. Field validation/config-building lives in settings_form.py
(no AppKit import, unit-tested); this module is a thin, untested shell
around it.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSButton,
    NSClosableWindowMask,
    NSMakeRect,
    NSObject,
    NSOffState,
    NSOnState,
    NSPopUpButton,
    NSSwitchButton,
    NSTextField,
    NSTitledWindowMask,
    NSWindow,
)

from .config_store import ConfigStore
from .dictation_app import DictationApp
from .settings_form import build_config_from_fields

WINDOW_WIDTH = 420
ROW_HEIGHT = 30
LABEL_WIDTH = 150
FIELD_X = LABEL_WIDTH + 20
FIELD_WIDTH = WINDOW_WIDTH - FIELD_X - 20
NUM_ROWS = 14

GRAMMAR_ENGINE_CHOICES = ["none", "languagetool", "gramformer"]
RECORDING_MODE_CHOICES = ["push_to_talk", "toggle"]
MODEL_SIZE_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]


class SettingsWindow(NSObject):
    """Owns the NSWindow and its controls for editing a DictationConfig."""

    def initWithDictationApp_(self, dictation_app: DictationApp):
        self = objc.super(SettingsWindow, self).init()
        if self is None:
            return None
        self.dictation_app = dictation_app
        self._build_window()
        return self

    def _build_window(self) -> None:
        config = self.dictation_app.config
        height = ROW_HEIGHT * NUM_ROWS + 20

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, WINDOW_WIDTH, height),
            NSTitledWindowMask | NSClosableWindowMask,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Whisper Dictation Settings")

        content = self.window.contentView()
        y = height - ROW_HEIGHT

        self.model_size_popup = self._add_popup(
            content, y, "Model size", MODEL_SIZE_CHOICES, config.model_size
        )
        y -= ROW_HEIGHT
        self.language_field = self._add_text_field(
            content, y, "Language", config.language or ""
        )
        y -= ROW_HEIGHT
        self.multilingual_checkbox = self._add_checkbox(
            content, y, "Multilingual", config.multilingual
        )
        y -= ROW_HEIGHT
        self.translate_checkbox = self._add_checkbox(
            content, y, "Translate to English", config.translate_to_english
        )
        y -= ROW_HEIGHT
        self.target_language_field = self._add_text_field(
            content, y, "Target language", config.target_language or ""
        )
        y -= ROW_HEIGHT
        self.grammar_engine_popup = self._add_popup(
            content, y, "Grammar engine", GRAMMAR_ENGINE_CHOICES,
            config.grammar_engine or "none",
        )
        y -= ROW_HEIGHT
        self.remove_fillers_checkbox = self._add_checkbox(
            content, y, "Remove fillers", config.remove_fillers
        )
        y -= ROW_HEIGHT
        self.hotwords_field = self._add_text_field(
            content, y, "Hotwords", ",".join(config.hotwords)
        )
        y -= ROW_HEIGHT
        self.audio_feedback_checkbox = self._add_checkbox(
            content, y, "Audio feedback", config.audio_feedback
        )
        y -= ROW_HEIGHT
        self.hotkey_field = self._add_text_field(
            content, y, "Record hotkey", "+".join(sorted(config.hotkey))
        )
        y -= ROW_HEIGHT
        self.recording_mode_popup = self._add_popup(
            content, y, "Recording mode", RECORDING_MODE_CHOICES, config.recording_mode
        )
        y -= ROW_HEIGHT
        replay_modifiers, replay_key = config.replay_hotkey
        self.replay_hotkey_field = self._add_text_field(
            content, y, "Replay hotkey",
            "+".join(sorted(replay_modifiers)) + f"+{replay_key}",
        )
        y -= ROW_HEIGHT

        self.status_field = self._add_label(content, y, "")
        y -= ROW_HEIGHT

        save_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(FIELD_X, y, 100, ROW_HEIGHT - 4)
        )
        save_button.setTitle_("Save")
        save_button.setBezelStyle_(1)
        save_button.setTarget_(self)
        save_button.setAction_("save:")
        content.addSubview_(save_button)

    def _add_label(self, content, y, text):
        label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, y, LABEL_WIDTH, 20))
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        content.addSubview_(label)
        return label

    def _add_text_field(self, content, y, label_text, value):
        self._add_label(content, y, label_text)
        field = NSTextField.alloc().initWithFrame_(
            NSMakeRect(FIELD_X, y, FIELD_WIDTH, 22)
        )
        field.setStringValue_(value)
        content.addSubview_(field)
        return field

    def _add_checkbox(self, content, y, label_text, value):
        checkbox = NSButton.alloc().initWithFrame_(
            NSMakeRect(FIELD_X, y, FIELD_WIDTH, 22)
        )
        checkbox.setButtonType_(NSSwitchButton)
        checkbox.setTitle_(label_text)
        checkbox.setState_(NSOnState if value else NSOffState)
        content.addSubview_(checkbox)
        return checkbox

    def _add_popup(self, content, y, label_text, choices, selected):
        self._add_label(content, y, label_text)
        popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(FIELD_X, y, FIELD_WIDTH, 22), False
        )
        popup.addItemsWithTitles_(choices)
        if selected in choices:
            popup.selectItemWithTitle_(selected)
        content.addSubview_(popup)
        return popup

    def _read_fields(self) -> dict:
        return {
            "model_size": self.model_size_popup.titleOfSelectedItem(),
            "language": self.language_field.stringValue(),
            "grammar_engine": self.grammar_engine_popup.titleOfSelectedItem(),
            "translate_to_english": bool(self.translate_checkbox.state()),
            "target_language": self.target_language_field.stringValue(),
            "multilingual": bool(self.multilingual_checkbox.state()),
            "remove_fillers": bool(self.remove_fillers_checkbox.state()),
            "hotwords": self.hotwords_field.stringValue(),
            "audio_feedback": bool(self.audio_feedback_checkbox.state()),
            "hotkey": self.hotkey_field.stringValue(),
            "recording_mode": self.recording_mode_popup.titleOfSelectedItem(),
            "replay_hotkey": self.replay_hotkey_field.stringValue(),
        }

    def save_(self, _sender):
        """PyObjC action method for the Save button (note the trailing `_`,
        which maps to the Objective-C selector `save:`)."""
        try:
            new_config = build_config_from_fields(
                self._read_fields(), base=self.dictation_app.config
            )
        except ValueError as e:
            self.status_field.setStringValue_(f"⚠️ {e}")
            return

        self.status_field.setStringValue_("Applying…")
        try:
            self.dictation_app.apply_config(new_config)
        except Exception as e:
            self.status_field.setStringValue_(f"⚠️ Could not apply: {e}")
            return

        ConfigStore().save(new_config)
        self.status_field.setStringValue_("Saved.")

    def show(self) -> None:
        self.window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)


def open_settings_window(dictation_app: DictationApp) -> SettingsWindow:
    """Create and show the settings window.

    Returns it so the caller (MenuBarApp) can keep a strong reference —
    without one, PyObjC can release the window before it's shown.
    """
    window = SettingsWindow.alloc().initWithDictationApp_(dictation_app)
    window.show()
    return window
```

- [ ] **Step 2: Run the full test suite (confirms the module at least imports cleanly)**

Run: `./venv/bin/python3 -c "import whisper_dictation.settings_window"`
Expected: no output, exit code 0

Run: `./venv/bin/python3 -m pytest tests/ -v`
Expected: PASS (unchanged — this task adds no new automated tests, `settings_form.py` already covers the testable logic)

- [ ] **Step 3: Commit**

```bash
git add whisper_dictation/settings_window.py
git commit -m "feat: add native AppKit settings window

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 8: cli.py wiring (--no-gui, config source resolution, GUI/headless launch)

**Files:**
- Modify: `whisper_dictation/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ConfigStore` (Task 2), `MenuBarApp` (Task 6), `DictationConfig.from_args` (existing).
- Produces: `_config_flags_passed(argv: list[str]) -> bool` (pure, testable).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python3 -m pytest tests/test_cli.py -v`
Expected: FAIL with `ImportError: cannot import name '_config_flags_passed'`

- [ ] **Step 3: Add `--no-gui` flag and config-source resolution**

In `whisper_dictation/cli.py`, add this import at the top (after the existing imports):

```python
from .config_store import ConfigStore
```

Add this function after the imports, before `def main():`:

```python
def _config_flags_passed(argv: list[str]) -> bool:
    """True if the user passed a config-affecting CLI flag.

    `--no-gui` doesn't count: it's a run-mode switch, not a config field,
    so a bare `--no-gui` still loads the saved config file.
    """
    return any(arg != "--no-gui" for arg in argv[1:])
```

Add the `--no-gui` argument in `main()`, right after the `--replay-hotkey` argument block:

```python
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help=(
            "Run headless (console only), skipping the menu bar app. "
            "Ignores the saved config file if any other flag is also passed."
        ),
    )
```

Replace this existing block:

```python
    args = parser.parse_args()

    try:
        config = DictationConfig.from_args(args)
    except ValueError as e:
        parser.error(str(e))
```

with:

```python
    args = parser.parse_args()

    try:
        if _config_flags_passed(sys.argv):
            config = DictationConfig.from_args(args)
        else:
            config = ConfigStore().load() or DictationConfig.from_args(args)
    except ValueError as e:
        parser.error(str(e))
```

Replace this existing block:

```python
    exit_code = 0
    try:
        app = DictationApp(config=config)
        app.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        exit_code = 1
```

with:

```python
    exit_code = 0
    try:
        app = DictationApp(config=config)
        if args.no_gui:
            app.run()
        else:
            from .menu_bar_app import MenuBarApp

            MenuBarApp(app).run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        exit_code = 1
```

Also add a `--no-gui` example to the epilog, right after the `--recording-mode toggle` example line:

```
  python dictation.py --no-gui                # Headless, no menu bar app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python3 -m pytest tests/ -v`
Expected: PASS (full suite)

- [ ] **Step 5: Commit**

```bash
git add whisper_dictation/cli.py tests/test_cli.py
git commit -m "feat: launch as a menu bar app by default, add --no-gui

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Manual verification (not automated — requires a real display and Accessibility/Input Monitoring permissions)**

Run: `./venv/bin/python3 dictation.py`

Check:
- A menu bar icon appears showing "🎙️ Idle".
- Dictating (hold/press the hotkey as configured) flips the icon to "🔴 Recording" and back.
- Menu → "Settings…" opens a window showing all current config values.
- Change a value (e.g. Recording Mode to "toggle"), click Save — status shows "Saved.", and the new mode takes effect immediately (test it) without restarting.
- Quit the app (Menu → Quit), restart it — confirm the changed setting persisted (check `~/.whisper_dictation/config.json` and that Settings shows the same value).
- Run `./venv/bin/python3 dictation.py --no-gui` — confirm it behaves exactly like before (console only, no menu bar icon).
- Run `./venv/bin/python3 dictation.py --model tiny` — confirm it starts with the `tiny` model regardless of whatever is saved in the config file (classic CLI-flags-override behavior).

---

### Task 9: README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the GUI mode**

Add a new section to `README.md`, after the existing "How It Works" / feature description section (wherever the toggle-mode/replay-hotkey paragraph from the previous feature was added), describing:
- The app now launches as a menu bar app by default (`python dictation.py`), with a "🎙️ Idle"/"🔴 Recording" status icon.
- Menu bar quick toggles for recording mode and audio feedback.
- "Settings…" opens a window covering the full configuration (model, language, translation, grammar, hotwords, audio feedback, hotkeys, recording mode) — changes apply immediately and persist to `~/.whisper_dictation/config.json`.
- `--no-gui` runs the previous headless console mode.
- Passing any other CLI flag uses that flag's value for the run instead of the saved config file (documented alongside the existing CLI options table — add a `--no-gui` row there too).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document menu bar app and settings window

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** menu bar icon/status (Task 6) ✓, quick toggles (Task 6) ✓, settings window covering every `DictationConfig` field except snippets (Task 7, matches spec's explicit scope) ✓, JSON persistence at `~/.whisper_dictation/config.json` (Task 2) ✓, live-apply without restart (Task 3) ✓, `--no-gui` (Task 8) ✓, startup precedence rule (Task 8) ✓, atomic `apply_config` error handling (Task 3, `test_invalid_new_config_leaves_previous_state_untouched`) ✓, `rumps` dependency (Task 6) ✓.
- **Type/name consistency checked:** `DictationApp.apply_config`, `_build_pipeline`, `start_background`, `poll_health`, `_print_banner` are defined once (Tasks 3-4) and referenced with matching names in Tasks 6-8; `ConfigStore(path=...)`/`.load()`/`.save()` signature is consistent between Task 2's definition and its Task 7/8 call sites; `build_config_from_fields(fields, base)` signature matches between Task 5's definition and Task 7's call site.
- **No placeholders:** every step has complete code, no TBD/"add appropriate handling" markers.
