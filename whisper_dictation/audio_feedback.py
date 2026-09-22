"""Audio feedback (beeps) for recording start/stop."""

from __future__ import annotations

import subprocess


class AudioFeedback:
    """Provides audio feedback for recording start/stop."""

    # Frequencies for different events (Hz)
    START_FREQ = 800
    STOP_FREQ = 600

    # Distinct system sounds so start and stop are audibly different.
    START_SOUND = "/System/Library/Sounds/Tink.aiff"
    STOP_SOUND = "/System/Library/Sounds/Pop.aiff"

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._procs: list[subprocess.Popen] = []

    def play_start(self):
        """Play sound indicating recording started."""
        if self.enabled:
            self._play_beep(self.START_FREQ, duration=0.1)

    def play_stop(self):
        """Play sound indicating recording stopped."""
        if self.enabled:
            self._play_beep(self.STOP_FREQ, duration=0.15, sound=self.STOP_SOUND)

    def _play_beep(self, frequency: int, duration: float, sound: str | None = None):
        """Play a system sound without ever blocking the caller.

        `afplay` is fired and forgotten: waiting for it (as a blocking
        subprocess call) could stall the keyboard event-tap callback long
        enough for macOS to disable the tap, killing the hotkey.
        """
        try:
            # Reap finished players so a long session cannot accumulate
            # zombie processes.
            self._procs = [p for p in self._procs if p.poll() is None]
            self._procs.append(
                subprocess.Popen(
                    ["afplay", sound or self.START_SOUND],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
        except Exception:
            # Silently fail if audio feedback doesn't work
            pass
