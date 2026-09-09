"""Main application window.

Flow: user clicks "Scan QR" (or presses the in-app Ctrl+Shift+Q accelerator)
-> area selection -> decode -> full raw text is always shown + copied.
If the payload is a well-formed `otpauth://` URI, `secret` and
`issuer`/publisher are additionally parsed out and shown with their own
Copy buttons, purely for convenience — the full raw text remains the
source of truth and is never altered.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from . import clipboard as clipboard_mod
from .config import Config
from .otp_parse import OtpFields
from .scanner import ScanOutcome, ScanResult, run_scan, send_notification, status_message
from .security import Event, log_event

_WINDOW_UI = """
<interface>
  <template class="QrTextReaderWindow" parent="AdwApplicationWindow">
    <property name="default-width">460</property>
    <property name="default-height">480</property>
    <property name="title">QR Text Reader</property>
    <child>
      <object class="GtkBox">
        <property name="orientation">vertical</property>
        <property name="spacing">12</property>
        <property name="margin-top">16</property>
        <property name="margin-bottom">16</property>
        <property name="margin-start">16</property>
        <property name="margin-end">16</property>

        <child>
          <object class="GtkButton" id="scan_button">
            <property name="label">Scan QR</property>
            <property name="tooltip-text">Ctrl+Shift+Q</property>
            <style>
              <class name="suggested-action"/>
              <class name="pill"/>
            </style>
          </object>
        </child>

        <child>
          <object class="GtkLabel">
            <property name="label">Raw text</property>
            <property name="xalign">0</property>
            <style><class name="heading"/></style>
          </object>
        </child>
        <child>
          <object class="GtkScrolledWindow">
            <property name="min-content-height">100</property>
            <property name="hscrollbar-policy">never</property>
            <child>
              <object class="GtkTextView" id="result_view">
                <property name="editable">false</property>
                <property name="wrap-mode">char</property>
                <property name="top-margin">8</property>
                <property name="bottom-margin">8</property>
                <property name="left-margin">8</property>
                <property name="right-margin">8</property>
                <style><class name="card"/></style>
              </object>
            </child>
          </object>
        </child>
        <child>
          <object class="GtkButton" id="copy_button">
            <property name="label">Copy full text</property>
            <property name="sensitive">false</property>
          </object>
        </child>

        <child>
          <object class="GtkSeparator" id="otp_separator">
            <property name="margin-top">4</property>
            <property name="margin-bottom">4</property>
            <property name="visible">false</property>
          </object>
        </child>

        <child>
          <object class="GtkBox" id="issuer_row">
            <property name="orientation">horizontal</property>
            <property name="spacing">8</property>
            <property name="visible">false</property>
            <child>
              <object class="GtkEntry" id="issuer_entry">
                <property name="editable">false</property>
                <property name="hexpand">true</property>
                <property name="placeholder-text">Issuer / publisher</property>
              </object>
            </child>
            <child>
              <object class="GtkButton" id="copy_issuer_button">
                <property name="label">Copy issuer</property>
              </object>
            </child>
          </object>
        </child>

        <child>
          <object class="GtkBox" id="secret_row">
            <property name="orientation">horizontal</property>
            <property name="spacing">8</property>
            <property name="visible">false</property>
            <child>
              <object class="GtkEntry" id="secret_entry">
                <property name="editable">false</property>
                <property name="hexpand">true</property>
                <property name="placeholder-text">Secret</property>
              </object>
            </child>
            <child>
              <object class="GtkButton" id="copy_secret_button">
                <property name="label">Copy secret</property>
                <style><class name="destructive-action"/></style>
              </object>
            </child>
          </object>
        </child>

        <child>
          <object class="GtkLabel" id="status_label">
            <property name="label">Ready</property>
            <property name="xalign">0</property>
            <property name="vexpand">true</property>
            <property name="valign">end</property>
            <style><class name="dim-label"/></style>
          </object>
        </child>
      </object>
    </child>
  </template>
</interface>
"""


@Gtk.Template(string=_WINDOW_UI)
class QrTextReaderWindow(Adw.ApplicationWindow):
    __gtype_name__ = "QrTextReaderWindow"

    scan_button: Gtk.Button = Gtk.Template.Child()
    copy_button: Gtk.Button = Gtk.Template.Child()
    result_view: Gtk.TextView = Gtk.Template.Child()
    status_label: Gtk.Label = Gtk.Template.Child()

    otp_separator: Gtk.Separator = Gtk.Template.Child()
    issuer_row: Gtk.Box = Gtk.Template.Child()
    issuer_entry: Gtk.Entry = Gtk.Template.Child()
    copy_issuer_button: Gtk.Button = Gtk.Template.Child()
    secret_row: Gtk.Box = Gtk.Template.Child()
    secret_entry: Gtk.Entry = Gtk.Template.Child()
    copy_secret_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, config: Config | None = None, **kwargs):
        super().__init__(**kwargs)
        self.config = config or Config.load()
        # Decoded values live ONLY in these in-process attributes (never
        # written to disk). Cleared at the start of every new scan.
        self._current_text: str | None = None
        self._current_secret: str | None = None
        self._current_issuer: str | None = None

        self.scan_button.connect("clicked", self._on_scan_clicked)
        self.copy_button.connect("clicked", self._on_copy_clicked)
        self.copy_secret_button.connect("clicked", self._on_copy_secret_clicked)
        self.copy_issuer_button.connect("clicked", self._on_copy_issuer_clicked)

        self._setup_shortcut()

    def _setup_shortcut(self) -> None:
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.LOCAL)
        shortcut = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Control><Shift>q"),
            Gtk.CallbackAction.new(lambda *_a: self.trigger_scan() or True),
        )
        controller.add_shortcut(shortcut)
        self.add_controller(controller)

    def _on_scan_clicked(self, _button: Gtk.Button) -> None:
        self.trigger_scan()

    def trigger_scan(self) -> None:
        self._reset_fields()
        self.status_label.set_label("Select an area on screen…")
        log_event(Event.SCAN_REQUESTED)

        display = self.get_display()
        result = run_scan(display, self.config)
        self.status_label.set_label(status_message(result.outcome))

        if result.outcome == ScanOutcome.SUCCESS and result.text is not None:
            self._apply_result(result)
        elif result.outcome == ScanOutcome.MULTIPLE:
            self._show_multiple_choice(result.all_texts)

    def _reset_fields(self) -> None:
        self._current_text = None
        self._current_secret = None
        self._current_issuer = None
        self.copy_button.set_sensitive(False)
        self._set_result_text("")
        self._show_otp_fields(None)

    def _apply_result(self, result: ScanResult) -> None:
        self._current_text = result.text
        self._set_result_text(result.text or "")
        self.copy_button.set_sensitive(True)
        self._show_otp_fields(result.otp_fields)

        if self.config.show_notification:
            body = "Copied to clipboard" if result.copied else "Decoded (copy failed)"
            send_notification(self.get_application(), "QR code detected", body)

    def _show_otp_fields(self, otp_fields: OtpFields | None) -> None:
        has_secret = bool(otp_fields and otp_fields.is_otpauth and otp_fields.secret)
        has_issuer = bool(otp_fields and otp_fields.is_otpauth and otp_fields.issuer)

        self.otp_separator.set_visible(has_secret or has_issuer)

        self._current_secret = otp_fields.secret if has_secret else None
        self.secret_row.set_visible(has_secret)
        self.secret_entry.set_text(self._current_secret or "")

        self._current_issuer = otp_fields.issuer if has_issuer else None
        self.issuer_row.set_visible(has_issuer)
        self.issuer_entry.set_text(self._current_issuer or "")

    def _show_multiple_choice(self, texts: tuple[str, ...]) -> None:
        """Let the user pick which of several detected QR codes to use.
        We never auto-select or merge them."""
        dialog = Adw.AlertDialog(
            heading="Multiple QR codes found",
            body="Select which QR code's text you want to use.",
        )
        for i, text in enumerate(texts):
            response_id = f"choice_{i}"
            preview = text if len(text) <= 40 else text[:37] + "..."
            dialog.add_response(response_id, preview)

        def _on_response(_dialog, response_id):
            if not response_id.startswith("choice_"):
                return
            idx = int(response_id.split("_", 1)[1])
            chosen = texts[idx]

            from .otp_parse import parse_otpauth

            copied = False
            if self.config.auto_copy:
                copied = clipboard_mod.copy_text(self.get_display(), chosen)

            fake_result = ScanResult(
                outcome=ScanOutcome.SUCCESS,
                text=chosen,
                copied=copied,
                otp_fields=parse_otpauth(chosen),
            )
            self._apply_result(fake_result)
            self.status_label.set_label("QR code detected")

        dialog.connect("response", _on_response)
        dialog.present(self)

    def _on_copy_clicked(self, _button: Gtk.Button) -> None:
        self._copy_value(self._current_text, "full text")

    def _on_copy_secret_clicked(self, _button: Gtk.Button) -> None:
        self._copy_value(self._current_secret, "secret")

    def _on_copy_issuer_clicked(self, _button: Gtk.Button) -> None:
        self._copy_value(self._current_issuer, "issuer")

    def _copy_value(self, value: str | None, label: str) -> None:
        if value is None:
            return
        ok = clipboard_mod.copy_text(self.get_display(), value)
        self.status_label.set_label(
            f"Copied {label} to clipboard" if ok else f"Could not copy {label}"
        )

    def _set_result_text(self, text: str) -> None:
        buf = self.result_view.get_buffer()
        buf.set_text(text)
