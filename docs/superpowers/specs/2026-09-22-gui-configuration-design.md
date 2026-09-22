# GUI Configuration — Design

## Purpose

The app is currently configured entirely via CLI flags and only runs as a
foreground/background console process with no persistent, discoverable UI.
This adds a macOS menu bar presence (status + quick toggles) and a settings
window covering the full configuration surface, with changes persisted to
disk and applied to the running app without a restart.

## Scope

In scope:
- Menu bar icon showing idle/recording status, with quick-toggle menu items
  and a "Settings…" entry.
- Native settings window covering every field in `DictationConfig`.
- JSON config file at `~/.whisper_dictation/config.json`, read/written by the
  GUI, loaded automatically on a flagless run.
- Live-apply of settings changes to the running `DictationApp` (no restart
  required).
- `--no-gui` flag to keep the existing headless console mode available.

Out of scope (YAGNI for this pass):
- Config file precedence merging with individual CLI flags (see "Startup
  precedence" below — CLI flags fully override the file for that run, they
  don't merge field-by-field).
- Any Linux/Windows GUI — this is macOS-only, matching the rest of the app's
  platform assumptions (pyobjc, CGEventTap).
- Auto-updating menu bar icon artwork/branding — plain text/emoji status is
  enough for v1.

## Architecture

`DictationApp.run()` currently does two things on the main thread: start the
pynput listener + worker thread, then block forever in a `while: time.sleep`
loop doing periodic health checks (`_resync_modifiers`, `_check_event_flow`).
A `rumps`-based menu bar app also needs to own the main thread's Cocoa run
loop, so the two can't coexist — the polling loop is replaced, not
duplicated, when running with a GUI.

- `DictationApp.run()` splits into:
  - `start_background()` — starts the worker thread and pynput listener,
    prints the startup banner. Returns immediately.
  - `run()` — calls `start_background()`, then keeps the existing polling
    `while` loop for headless mode. Behavior for `--no-gui` is unchanged.
- `MenuBarApp(rumps.App)` (new, `whisper_dictation/menu_bar_app.py`):
  - Calls `dictation_app.start_background()`, then `rumps.App.run()` takes
    the main thread.
  - `@rumps.timer(0.5)` callback replaces the headless polling loop's body:
    `_resync_modifiers()`, `_check_event_flow()`, updates the menu bar
    title/icon between "Idle" and "● Recording", and calls
    `rumps.quit_application()` if `dictation_app.running` has gone `False`
    (e.g. Escape was pressed).
  - Menu: status line (disabled item), recording mode toggle, audio feedback
    toggle, "Settings…", "Quit".
- `SettingsWindow` (new, `whisper_dictation/settings_window.py`), built
  directly with PyObjC/AppKit (`NSWindow`, `NSPopUpButton`, `NSButton`,
  `NSTextField`) rather than a second GUI toolkit (e.g. Tkinter) — one
  native event loop, no run-loop conflicts with `rumps`.
  - Fields: model size, language, multilingual, translate-to-English,
    target language, grammar engine, remove fillers, hotwords, audio
    feedback, record hotkey, recording mode, replay hotkey.
  - "Save" parses/validates field values (reusing
    `DictationConfig._parse_hotkey` / `_parse_replay_hotkey`), writes the
    resulting `DictationConfig` via `ConfigStore.save()`, and calls
    `dictation_app.apply_config(new_config)`.
- `DictationApp.apply_config(new_config)` (new method):
  - Updates lightweight live attributes immediately under `self.lock`:
    `hotkey`, `recording_mode`, `replay_hotkey`, `audio_feedback.enabled`,
    filler-removal processor presence.
  - Recreates heavier components in place when their inputs changed:
    `Transcriber` (model size, language, multilingual, hotwords,
    translate_to_english) and the grammar corrector (grammar_engine,
    language). This takes a moment (model reload) — the settings window
    shows an "Applying…" state during the call rather than hiding the
    delay.
  - Sets `self.config = new_config` at the end.
- `ConfigStore` (new, `whisper_dictation/config_store.py`):
  - Path: `~/.whisper_dictation/config.json`.
  - `load() -> DictationConfig | None` — returns `None` if the file doesn't
    exist or fails to parse (falls back to defaults, doesn't crash startup).
  - `save(config: DictationConfig) -> None`.
  - Uses new `DictationConfig.to_json_dict()` / `.from_json_dict()` methods
    to serialize `hotkey` (a `set[str]` → sorted list) and `replay_hotkey`
    (`tuple[frozenset[str], str]` → `{"modifiers": [...], "key": "v"}`).

## Startup precedence

Running `python dictation.py` with **no CLI flags**:
- Loads `~/.whisper_dictation/config.json` if it exists (so GUI-made changes
  persist across restarts); otherwise uses hardcoded defaults.
- Launches the menu bar app (GUI is the default) unless `--no-gui` is passed.

Running `python dictation.py` with **any CLI flags**:
- Uses classic argparse-only behavior for that run (`DictationConfig.from_args`,
  unchanged) — the saved config file is ignored entirely and nothing is
  persisted from CLI flags.
- This keeps CLI usage simple (no per-field merge logic) at the cost of CLI
  flags and the GUI not composing in the same run — acceptable since the two
  are different personas (scripting/testing vs. everyday use).

`--no-gui` forces headless console mode regardless of the above (still
respects the config-file-when-no-other-flags rule).

## Data flow

1. App starts → `cli.py` decides config source (file vs. args) → builds
   `DictationConfig` → builds `DictationApp(config=...)`.
2. GUI mode: `MenuBarApp(dictation_app)` starts background threads, takes
   over the main thread.
3. User opens Settings, changes a field, clicks Save →
   `SettingsWindow` validates → `ConfigStore.save(new_config)` (disk) →
   `dictation_app.apply_config(new_config)` (live).
4. Quick toggles in the menu bar (recording mode, audio feedback) go through
   the same `apply_config` path with a minimally-changed `DictationConfig`,
   so there's one code path for "settings changed," not two.

## Error handling

- `ConfigStore.load()` catches JSON/OS errors, logs a warning, returns
  `None` (defaults apply) — a corrupt config file must never prevent
  startup.
- `apply_config()` validates before mutating: if hotkey/replay-hotkey
  parsing fails, the settings window shows the error inline and nothing is
  applied or saved (matches today's CLI behavior of rejecting bad specs
  loudly rather than silently).
- If `Transcriber`/grammar corrector re-init raises (e.g. unknown model
  size), `apply_config` leaves the previous instances in place and surfaces
  the error rather than leaving `DictationApp` in a half-updated state.

## Testing

Unit-testable (same mocking patterns as existing tests):
- `ConfigStore.save`/`load` round-trip, missing file, corrupt JSON.
- `DictationConfig.to_json_dict`/`from_json_dict` round-trip, including
  `hotkey`/`replay_hotkey`.
- `DictationApp.apply_config()`: live attributes update; `Transcriber`/
  grammar corrector recreated only when relevant fields change (mocked,
  matching existing `Transcriber` test patterns); invalid hotkey spec
  raises and leaves state untouched.

Not unit-testable (requires a real macOS window server / NSApplication):
- `MenuBarApp` menu construction and timer behavior.
- `SettingsWindow` rendering and field round-trip through the actual UI.

These will be verified by running the app and checking behavior directly,
the same way the toggle-mode and replay-hotkey feature was verified.

## New dependency

- `rumps` (thin wrapper over the `pyobjc-framework-Cocoa` already in
  `requirements.txt`) — added to `requirements.txt`.
