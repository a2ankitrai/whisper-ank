"""Types text into the currently focused application using macOS CGEvents."""

from __future__ import annotations

import ctypes
import time

from ApplicationServices import (
    AXIsProcessTrusted,
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    kCGHIDEventTap,
    CGEventSourceCreate,
    CGEventSetFlags,
    kCGEventSourceStateHIDSystemState,
)
from Quartz.CoreGraphics import CGEventKeyboardSetUnicodeString

# Not exposed by pyobjc; Carbon has no Python binding for this check.
_carbon = ctypes.CDLL(
    "/System/Library/Frameworks/Carbon.framework/Carbon"
)
_carbon.IsSecureEventInputEnabled.restype = ctypes.c_bool


def _ensure_accessibility_permission() -> None:
    """Request Accessibility access once, up front, if not already granted.

    Without this permission, CGEventPost silently drops every synthetic
    keystroke: transcription and processing still run, but no text ever
    appears anywhere, with no error raised. Passing the prompt option makes
    macOS show its native permission dialog immediately instead of leaving
    the user to discover this only after dictating into empty air.
    """
    trusted = AXIsProcessTrustedWithOptions(
        {kAXTrustedCheckOptionPrompt: True}
    )
    if not trusted:
        print(
            "⚠️  Accessibility permission is required to type dictated text.\n"
            "   Grant it in System Settings > Privacy & Security > "
            "Accessibility\n"
            "   (enable your terminal app, e.g. iTerm2 or Terminal), then "
            "restart dictation."
        )


def _frontmost_app_name() -> str:
    """Best-effort name of the app that currently has keyboard focus."""
    try:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.localizedName() if app else "unknown"
    except Exception:
        return "unknown"


class TextTyper:
    """Types text into the currently focused application using macOS CGEvents."""

    def __init__(self):
        self.source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState)
        _ensure_accessibility_permission()

    def type_text(self, text: str):
        """Type text character by character into the focused app."""
        if not text:
            return

        # Defense in depth: permission can be revoked mid-session (e.g. the
        # user removes the app from System Settings), and Secure Keyboard
        # Entry can be toggled on by any app at any time. Both silently
        # drop every keystroke with no exception, so re-check on every call.
        if not AXIsProcessTrusted():
            print(
                "⚠️  Accessibility permission not granted to this process; "
                "typed text will not appear anywhere."
            )
        if _carbon.IsSecureEventInputEnabled():
            print(
                f"⚠️  macOS Secure Keyboard Entry is active (frontmost app: "
                f"{_frontmost_app_name()}); synthetic typing is blocked "
                f"system-wide until it's turned off."
            )

        for char in text:
            self._type_char(char)
            time.sleep(0.008)  # Small delay for reliability

    def _type_char(self, char: str):
        """Type a single Unicode character."""
        event_down = CGEventCreateKeyboardEvent(self.source, 0, True)
        event_up = CGEventCreateKeyboardEvent(self.source, 0, False)

        # Typing runs on a background thread, so the user may already be
        # holding modifiers again (e.g. starting the next dictation). Without
        # clearing the inherited flags those characters would be delivered as
        # keyboard shortcuts instead of text.
        CGEventSetFlags(event_down, 0)
        CGEventSetFlags(event_up, 0)

        CGEventKeyboardSetUnicodeString(event_down, len(char), char)
        CGEventKeyboardSetUnicodeString(event_up, len(char), char)

        CGEventPost(kCGHIDEventTap, event_down)
        CGEventPost(kCGHIDEventTap, event_up)
