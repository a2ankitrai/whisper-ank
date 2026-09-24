"""Dock name and icon for the menu bar app (thin AppKit shell, untested)."""

from __future__ import annotations

from AppKit import (
    NSApplication,
    NSAttributedString,
    NSBundle,
    NSFont,
    NSFontAttributeName,
    NSImage,
    NSMakeRect,
)
from Foundation import NSMakeSize

APP_NAME = "WisperAnk"
ICON_EMOJI = "🎙️"
ICON_SIZE = 512


def _render_icon() -> NSImage:
    """Draw the emoji into an NSImage so no icon asset file is needed."""
    image = NSImage.alloc().initWithSize_(NSMakeSize(ICON_SIZE, ICON_SIZE))
    text = NSAttributedString.alloc().initWithString_attributes_(
        ICON_EMOJI, {NSFontAttributeName: NSFont.systemFontOfSize_(ICON_SIZE * 0.8)}
    )
    text_size = text.size()
    image.lockFocus()
    text.drawInRect_(
        NSMakeRect(
            (ICON_SIZE - text_size.width) / 2,
            (ICON_SIZE - text_size.height) / 2,
            text_size.width,
            text_size.height,
        )
    )
    image.unlockFocus()
    return image


def apply_app_identity() -> None:
    """Replace the Python rocket icon and "Python" name shown in the Dock."""
    info = NSBundle.mainBundle().infoDictionary()
    info["CFBundleName"] = APP_NAME
    info["CFBundleDisplayName"] = APP_NAME
    NSApplication.sharedApplication().setApplicationIconImage_(_render_icon())
