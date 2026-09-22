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
