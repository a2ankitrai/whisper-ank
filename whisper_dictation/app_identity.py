"""Dock name and icon for the menu bar app (thin AppKit shell, untested)."""

from __future__ import annotations

from AppKit import (
    NSApplication,
    NSAttributedString,
    NSBundle,
    NSFont,
    NSFontAttributeName,
    NSImage,
    NSBitmapImageRep,
    NSMakeRect,
    NSPNGFileType,
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


def render_icon_png(path: str) -> None:
    """Write the icon to a PNG file (used by build_app.sh for the .icns)."""
    tiff = _render_icon().TIFFRepresentation()
    png = NSBitmapImageRep.imageRepWithData_(tiff).representationUsingType_properties_(
        NSPNGFileType, None
    )
    png.writeToFile_atomically_(path, True)


def apply_app_identity() -> None:
    """Replace the Python rocket icon and "Python" name shown in the Dock."""
    info = NSBundle.mainBundle().infoDictionary()
    info["CFBundleName"] = APP_NAME
    info["CFBundleDisplayName"] = APP_NAME
    NSApplication.sharedApplication().setApplicationIconImage_(_render_icon())


_dock_actions: dict = {}


def install_dock_handlers(open_settings, quit_app) -> None:
    """Make the Dock icon usable: right-click menu, and click/relaunch opens Settings.

    Adds delegate methods to rumps' NSApplication delegate class, so the app is
    controllable even when its menu bar item is hidden (e.g. a crowded menu bar).
    """
    import objc
    from AppKit import NSMenu, NSMenuItem
    from rumps.rumps import NSApp as _RumpsNSApp

    _dock_actions["settings"] = open_settings
    _dock_actions["quit"] = quit_app

    class NSApp(objc.Category(_RumpsNSApp)):  # name must match the target class
        def applicationShouldHandleReopen_hasVisibleWindows_(self, app, has_windows):
            _dock_actions["settings"]()
            return False

        def dockOpenSettings_(self, sender):
            _dock_actions["settings"]()

        def dockQuit_(self, sender):
            _dock_actions["quit"]()

        def applicationDockMenu_(self, app):
            menu = NSMenu.alloc().init()
            for title, action in (("Settings…", "dockOpenSettings:"), ("Quit", "dockQuit:")):
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
                item.setTarget_(self)
                menu.addItem_(item)
            return menu
