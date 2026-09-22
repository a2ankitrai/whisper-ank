"""Keyboard/modifier helpers and a pynput listener that can heal itself.

macOS silently disables an event tap whose callback is too slow
(`kCGEventTapDisabledByTimeout`) and pynput never re-enables it, so the
hotkey stops working until the app is restarted. `_resilient_listener_class`
keeps a handle on the tap so the app can detect that and switch it back on.
"""

from __future__ import annotations

# macOS-specific imports for keyboard simulation and event-tap health checks
from Quartz import (
    CGEventSourceFlagsState,
    CGEventTapEnable,
    CGEventTapIsEnabled,
    kCGEventSourceStateCombinedSessionState,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
)

#: Live modifier flag masks, used to re-synchronise our key state with the OS.
MODIFIER_FLAG_MASKS = {
    "cmd": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "ctrl": kCGEventFlagMaskControl,
    "alt": kCGEventFlagMaskAlternate,
}


def live_modifiers() -> set[str]:
    """Return the modifiers that are *physically* held down right now.

    Reading the hardware state lets us recover from press/release events that
    were never delivered (e.g. while the event tap was disabled).
    """
    flags = CGEventSourceFlagsState(kCGEventSourceStateCombinedSessionState)
    return {name for name, mask in MODIFIER_FLAG_MASKS.items() if flags & mask}


def key_to_char(key) -> str | None:
    """Return a lowercase single-character label for a plain (non-modifier) key.

    Used to match the trailing key of a modifier+key hotkey spec (e.g. the
    'v' in cmd+shift+v). Special keys (arrows, esc, etc.) have no `.char`
    attribute and correctly return None.
    """
    char = getattr(key, "char", None)
    if not char:
        return None
    return char.lower()


_RESILIENT_LISTENER_CLS = None


def _resilient_listener_class():
    """Build (once) a pynput listener that exposes its macOS event tap.

    macOS silently disables an event tap whose callback is too slow
    (`kCGEventTapDisabledByTimeout`) and pynput never re-enables it, so the
    hotkey stops working until the app is restarted. Keeping a handle on the
    tap lets us detect that and switch it back on.
    """
    global _RESILIENT_LISTENER_CLS
    if _RESILIENT_LISTENER_CLS is None:
        from pynput import keyboard

        class ResilientListener(keyboard.Listener):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._event_tap = None

            def _create_event_tap(self):
                self._event_tap = super()._create_event_tap()
                return self._event_tap

            def ensure_tap_enabled(self) -> bool:
                """Re-enable the tap if macOS disabled it. True if it was dead."""
                tap = self._event_tap
                if tap is None:
                    return False
                try:
                    if CGEventTapIsEnabled(tap):
                        return False
                    CGEventTapEnable(tap, True)
                    return True
                except Exception:
                    return False

        _RESILIENT_LISTENER_CLS = ResilientListener
    return _RESILIENT_LISTENER_CLS
