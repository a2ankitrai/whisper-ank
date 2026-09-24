"""Keyboard/modifier helpers and a pynput listener that can heal itself.

macOS silently disables an event tap whose callback is too slow
(`kCGEventTapDisabledByTimeout`) and pynput never re-enables it, so the
hotkey stops working until the app is restarted. `_resilient_listener_class`
keeps a handle on the tap so the app can detect that and switch it back on.
"""

from __future__ import annotations

# macOS-specific imports for keyboard simulation and event-tap health checks
from Quartz import (
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventSourceFlagsState,
    CGEventTapEnable,
    CGEventTapIsEnabled,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGKeyboardEventKeycode,
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


#: ANSI virtual keycodes for the keys allowed as the trailing key of a
#: modifier+key record hotkey. Matched by keycode, not character, because
#: Option turns 'd' into '∂' in the event's character.
KEY_CODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38,
    "k": 40, "n": 45, "m": 46,
}


def key_matches(key, target: str) -> bool:
    """True if a pynput key is the plain key named `target` (e.g. 'd').

    Compares the virtual keycode first so it still matches while Option (or
    another modifier) changes the produced character.
    """
    expected = KEY_CODES.get(target)
    if expected is not None and getattr(key, "vk", None) == expected:
        return True
    return key_to_char(key) == target


def make_hotkey_intercept(get_hotkey):
    """Build a pynput `intercept` callback that swallows the record hotkey.

    Without this, Option+D would also type '∂' into the focused window.
    `get_hotkey()` returns (modifiers, key) or (modifiers, None); the
    callback runs inside the event tap, so it must stay cheap.
    """

    def intercept(event_type, event):
        if event_type not in (kCGEventKeyDown, kCGEventKeyUp):
            return event
        modifiers, key = get_hotkey()
        expected = KEY_CODES.get(key) if key else None
        if expected is None:
            return event
        if CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode) != expected:
            return event
        flags = CGEventGetFlags(event)
        if all(flags & MODIFIER_FLAG_MASKS[m] for m in modifiers):
            return None
        return event

    return intercept


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
