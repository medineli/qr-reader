"""Application entry point.

Single mode: `qr-text-reader` opens the main window. Scanning always happens
from inside that window — via the "Scan QR" button or the in-app
Ctrl+Shift+Q shortcut (active while the window has focus). There is no
headless/background scan mode: every scan result is always visible in the
window, so the user always sees exactly what was decoded and copied.
"""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from .config import Config
from .security import Event, log_event
from .window import QrTextReaderWindow

APP_ID = "com.example.QRTextReader"


class QrTextReaderApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window: QrTextReaderWindow | None = None
        self.config = Config.load()

    def do_startup(self):
        Adw.Application.do_startup(self)
        log_event(Event.APP_STARTED)

    def do_activate(self):
        if self.window is None:
            self.window = QrTextReaderWindow(application=self, config=self.config)
        self.window.present()


def run() -> int:
    app = QrTextReaderApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(run())
