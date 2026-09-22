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
        # Self-heal the menu's own display: config can also change via the
        # Settings window's Save button (a separate code path from these
        # menu items' own toggle handlers), which would otherwise leave the
        # recording-mode label and audio-feedback checkmark stale.
        self._sync_recording_mode_label()
        self.audio_feedback_item.state = self.dictation_app.config.audio_feedback
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
        # Reuse the existing window controller rather than building a new
        # one on every click: a fresh SettingsWindow would overwrite our
        # only Python-side reference to the previous one while its NSWindow
        # (with a Save button targeting the now-unreferenced old controller)
        # is still on screen — a deallocated-target crash risk. Tradeoff:
        # the fields won't pick up changes made outside this window (e.g. a
        # saved-config edit elsewhere) until it's recreated, which is
        # acceptable for this low-risk cleanup.
        if self._settings_window is not None:
            self._settings_window.show()
            return

        from .settings_window import open_settings_window

        # Keep a reference so ARC/PyObjC doesn't release the window early.
        self._settings_window = open_settings_window(self.dictation_app)

    def _quit(self, _sender):
        self.dictation_app.running = False
        rumps.quit_application()
