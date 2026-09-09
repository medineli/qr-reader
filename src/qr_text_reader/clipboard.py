"""Clipboard access via GTK4's Gdk.Clipboard (Wayland-native, no portal needed
since it goes through our own window's display connection).

Note on Wayland clipboard semantics (documented, not just in comments, so the
UI can also surface this to the user — see window.py status text):
Under Wayland, an application's clipboard offer typically only remains valid
while the application is running (or until another app takes ownership).
GNOME's clipboard manager behavior can vary. We do not promise the copied
text will "survive" indefinitely after this application exits.
"""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib  # noqa: E402

from .security import Event, log_error, log_event


def copy_text(display: Gdk.Display, text: str) -> bool:
    """Copy `text` to the system clipboard. Returns True on success.
    Never logs `text` itself.
    """
    try:
        clipboard = display.get_clipboard()
        clipboard.set(text)
        log_event(Event.CLIPBOARD_OK)
        return True
    except GLib.Error as exc:
        log_error(Event.CLIPBOARD_FAILED, exc)
        return False


def schedule_clear(
    display: Gdk.Display,
    seconds: int,
    expected_text: str,
    on_cleared: Callable[[], None] | None = None,
) -> int | None:
    """Schedule clearing the clipboard after `seconds`, but ONLY if the
    clipboard still contains exactly what we put there (so we don't wipe out
    something the user copied afterwards). Returns the GLib source id, or
    None if seconds <= 0 (auto-clear disabled).
    """
    if seconds <= 0:
        return None

    def _clear():
        clipboard = display.get_clipboard()

        def _on_read(_clipboard, result):
            try:
                current = clipboard.read_text_finish(result)
            except GLib.Error:
                current = None
            if current == expected_text:
                clipboard.set("")
                if on_cleared:
                    on_cleared()

        clipboard.read_text_async(None, _on_read)
        return False  # do not repeat

    return GLib.timeout_add_seconds(seconds, _clear)
