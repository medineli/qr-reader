"""Wayland-native, portal-based screen capture.

We deliberately do NOT implement our own screen-darkening / rectangle-selection
overlay. On Wayland, applications cannot capture the screen directly for
security reasons — the compositor mediates this through
`org.freedesktop.portal.Screenshot`. Calling it with `interactive: true`
makes GNOME Shell show its own native region-selection UI, which is exactly
the "dim screen -> drag a rectangle" experience requested, but implemented
by the compositor itself (the only place allowed to do it safely).

The portal writes the screenshot to a short-lived file (its own temp
location, outside our control) and returns a `file://` URI. We read it into
memory immediately and delete it ourselves as soon as possible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from .security import Event, log_error, log_event, secure_delete

PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_OBJECT_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_IFACE = "org.freedesktop.portal.Request"

_TIMEOUT_SECONDS = 120  # generous, since the user is interactively selecting


class ScreenshotError(Exception):
    """Raised when the portal is unavailable, the user cancels, or capture fails."""


class ScreenshotCancelled(ScreenshotError):
    """Raised specifically when the user cancels the selection (e.g. Escape)."""


@dataclass
class CapturedImage:
    """In-memory image bytes. `data` should be cleared by the caller (best
    effort — CPython bytes are immutable, so we drop all references and let
    the object become garbage as soon as decoding is done)."""

    data: bytes
    mime_hint: str = "image/png"


def _unique_token() -> str:
    return f"qrtr{int(time.time() * 1000)}"


def take_interactive_screenshot(parent_window_handle: str = "") -> CapturedImage:
    """Invoke the desktop portal's interactive screenshot flow and return the
    captured image bytes, having already deleted the portal's temp file.

    Raises ScreenshotCancelled if the user cancels, ScreenshotError otherwise.
    """
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    except GLib.Error as exc:
        log_error(Event.PORTAL_UNAVAILABLE, exc)
        raise ScreenshotError("Could not connect to the session D-Bus.") from exc

    sender = connection.get_unique_name().lstrip(":").replace(".", "_")
    token = _unique_token()
    request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

    result: dict = {}
    loop = GLib.MainLoop()

    def on_response(_conn, _sender_name, _path, _iface, _signal, params):
        code, results = params.unpack()
        result["code"] = code
        result["results"] = results
        loop.quit()

    sub_id = connection.signal_subscribe(
        PORTAL_BUS_NAME,
        PORTAL_REQUEST_IFACE,
        "Response",
        request_path,
        None,
        Gio.DBusSignalFlags.NONE,
        on_response,
    )

    try:
        # IMPORTANT: pass a plain dict here, NOT a pre-built GLib.Variant.
        # PyGObject's GLib.Variant("(sa{sv})", (...)) constructor builds the
        # nested "a{sv}" itself from a dict of {str: GLib.Variant}. Handing
        # it an already-built GLib.Variant for the second tuple element
        # makes the override try to iterate/index it like a dict, which
        # raises `KeyError: 0`.
        options = {
            "handle_token": GLib.Variant("s", token),
            "interactive": GLib.Variant("b", True),
        }
        connection.call_sync(
            PORTAL_BUS_NAME,
            PORTAL_OBJECT_PATH,
            PORTAL_SCREENSHOT_IFACE,
            "Screenshot",
            GLib.Variant("(sa{sv})", (parent_window_handle, options)),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )

        def _timeout():
            loop.quit()
            return False

        timeout_id = GLib.timeout_add_seconds(_TIMEOUT_SECONDS, _timeout)
        loop.run()
        GLib.source_remove(timeout_id)
    except GLib.Error as exc:
        log_error(Event.SCREENSHOT_FAILED, exc)
        raise ScreenshotError("The screenshot portal call failed.") from exc
    finally:
        connection.signal_unsubscribe(sub_id)

    if "code" not in result:
        raise ScreenshotError("Screenshot request timed out.")

    if result["code"] == 1:
        log_event(Event.SCREENSHOT_CANCELLED)
        raise ScreenshotCancelled("User cancelled the screenshot selection.")
    if result["code"] != 0:
        log_event(Event.SCREENSHOT_FAILED)
        raise ScreenshotError("Screenshot portal returned an error.")

    uri = result["results"].get("uri")
    if not uri:
        raise ScreenshotError("Screenshot portal returned no image URI.")

    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ScreenshotError("Unexpected screenshot URI scheme.")

    path = Path(unquote(parsed.path))
    try:
        data = path.read_bytes()
    except OSError as exc:
        log_error(Event.SCREENSHOT_FAILED, exc)
        raise ScreenshotError("Could not read the captured screenshot file.") from exc
    finally:
        secure_delete(path)

    log_event(Event.SCREENSHOT_OK)
    return CapturedImage(data=data)
