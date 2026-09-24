"""Native macOS settings window (PyObjC/AppKit) for GUI-driven configuration.

Built directly on AppKit rather than a second GUI toolkit (e.g. Tkinter) so
there's exactly one native event loop, matching the rumps-based MenuBarApp
that owns it. Field validation/config-building lives in settings_form.py
(no AppKit import, unit-tested); this module is a thin, untested shell
around it.
"""

from __future__ import annotations

import subprocess
import threading

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
from PyObjCTools import AppHelper

from .config import ensure_dictionary_file
from .config_store import ConfigStore
from .dictation_app import DictationApp
from .settings_form import build_config_from_fields

WINDOW_WIDTH = 420
ROW_HEIGHT = 30
LABEL_WIDTH = 150
FIELD_X = LABEL_WIDTH + 20
FIELD_WIDTH = WINDOW_WIDTH - FIELD_X - 20
NUM_ROWS = 15

GRAMMAR_ENGINE_CHOICES = ["none", "languagetool", "gramformer"]
RECORDING_MODE_CHOICES = ["push_to_talk", "toggle"]
MODEL_SIZE_CHOICES = ["tiny", "base", "small", "medium", "large-v3"]

# faster_whisper's supported language codes (faster_whisper.tokenizer's
# private _LANGUAGE_CODES, copied here as a plain list rather than importing
# a private attribute — this set has been stable across Whisper releases).
# "auto" maps to language=None (Whisper auto-detects).
LANGUAGE_CHOICES = ["auto"] + [
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs",
    "ca", "cs", "cy", "da", "de", "el", "en", "es", "et", "eu", "fa", "fi",
    "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi", "hr", "ht", "hu", "hy",
    "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb",
    "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru",
    "sa", "sd", "si", "sk", "sl", "sn", "so", "sq", "sr", "su", "sv", "sw",
    "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi",
    "yi", "yo", "yue", "zh",
]

# Best-effort snapshot of languages Argos Translate can translate English
# into. Argos's real availability comes from a live, downloadable package
# index (see translator.py), which this list doesn't track — an entry that's
# actually unavailable just degrades to the "package not found" warning
# translator.py already prints, the same failure mode free text had.
# "none" maps to target_language=None (no post-translation step).
TARGET_LANGUAGE_CHOICES = ["none"] + [
    "ar", "az", "bg", "bn", "ca", "cs", "da", "de", "el", "eo", "es", "et",
    "eu", "fa", "fi", "fr", "ga", "gl", "he", "hi", "hu", "id", "it", "ja",
    "ko", "lt", "lv", "ms", "nb", "nl", "pl", "pt", "ro", "ru", "sk", "sl",
    "sq", "sv", "th", "tl", "tr", "uk", "ur", "vi", "zh", "zt",
]


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
        # Without this, closing the window (its default close button) releases
        # it out from under the Python-side controller, since NSWindow
        # defaults releasedWhenClosed to True — an over-release risk given we
        # keep our own strong reference to reuse the window on reopen.
        self.window.setReleasedWhenClosed_(False)

        content = self.window.contentView()
        y = height - ROW_HEIGHT

        self.model_size_popup = self._add_popup(
            content, y, "Model size", MODEL_SIZE_CHOICES, config.model_size
        )
        y -= ROW_HEIGHT
        self.language_popup = self._add_popup(
            content, y, "Language", LANGUAGE_CHOICES, config.language or "auto"
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
        self.target_language_popup = self._add_popup(
            content, y, "Target language", TARGET_LANGUAGE_CHOICES,
            config.target_language or "none",
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
        self._add_label(content, y, "Dictionary")
        dictionary_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(FIELD_X, y, FIELD_WIDTH, 24)
        )
        dictionary_button.setTitle_("Open dictionary file…")
        dictionary_button.setBezelStyle_(1)
        dictionary_button.setTarget_(self)
        dictionary_button.setAction_("openDictionary:")
        content.addSubview_(dictionary_button)
        self.dictionary_button = dictionary_button
        y -= ROW_HEIGHT
        self.audio_feedback_checkbox = self._add_checkbox(
            content, y, "Audio feedback", config.audio_feedback
        )
        y -= ROW_HEIGHT
        self.hotkey_field = self._add_text_field(
            content, y, "Record hotkey",
            "+".join(sorted(config.hotkey) + ([config.hotkey_key] if config.hotkey_key else [])),
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
        self.save_button = save_button

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
            "language": self.language_popup.titleOfSelectedItem(),
            "grammar_engine": self.grammar_engine_popup.titleOfSelectedItem(),
            "translate_to_english": bool(self.translate_checkbox.state()),
            "target_language": self.target_language_popup.titleOfSelectedItem(),
            "multilingual": bool(self.multilingual_checkbox.state()),
            "remove_fillers": bool(self.remove_fillers_checkbox.state()),
            "hotwords": self.hotwords_field.stringValue(),
            "audio_feedback": bool(self.audio_feedback_checkbox.state()),
            "hotkey": self.hotkey_field.stringValue(),
            "recording_mode": self.recording_mode_popup.titleOfSelectedItem(),
            "replay_hotkey": self.replay_hotkey_field.stringValue(),
        }

    def openDictionary_(self, _sender):
        """Open the dictionary file in the default text editor (creating it
        first if needed). Edits apply the next time Save is pressed."""
        path = ensure_dictionary_file(self.dictation_app.config.dictionary_path)
        subprocess.run(["open", "-t", str(path)], check=False)
        self.status_field.setStringValue_("Edit the file, then press Save to apply")

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

        # apply_config() can trigger a Transcriber reload, which loads (and,
        # on first use of a given model size, downloads) a Whisper model —
        # this can take anywhere from seconds to minutes. Running it here,
        # on the main thread, would block the whole Cocoa run loop for that
        # entire time: the window (and the rumps menu bar, which shares this
        # thread) would stop responding to any input, with no way to tell
        # that from "crashed". Do the apply on a background thread instead
        # and hop back to the main thread only to update the UI.
        self.status_field.setStringValue_("Applying…")
        self.save_button.setEnabled_(False)

        def apply_in_background():
            try:
                self.dictation_app.apply_config(new_config)
                ConfigStore().save(new_config)
            except Exception as e:
                AppHelper.callAfter(self._on_apply_failed, e)
            else:
                AppHelper.callAfter(self._on_apply_succeeded)

        threading.Thread(target=apply_in_background, daemon=True).start()

    def _on_apply_succeeded(self) -> None:
        self.status_field.setStringValue_("Saved.")
        self.save_button.setEnabled_(True)

    def _on_apply_failed(self, error: Exception) -> None:
        self.status_field.setStringValue_(f"⚠️ Could not apply: {error}")
        self.save_button.setEnabled_(True)

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
