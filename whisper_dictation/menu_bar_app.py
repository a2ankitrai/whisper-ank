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
