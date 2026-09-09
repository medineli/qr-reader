"""Orchestrates a single scan: screenshot -> decode -> (auto-copy) -> result.

This is the only module that ties the other pieces together, so the security-
sensitive data flow (raw QR text) stays inside a small, auditable surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gdk, Gio, GLib  # noqa: E402

from . import clipboard as clipboard_mod
from .config import Config
from .decoder import DecodeStatus, decode_qr
from .otp_parse import OtpFields, parse_otpauth
from .screenshot import ScreenshotCancelled, ScreenshotError, take_interactive_screenshot


class ScanOutcome(Enum):
    SUCCESS = auto()
    MULTIPLE = auto()
    NOT_FOUND = auto()
    EMPTY_PAYLOAD = auto()
    INVALID_IMAGE = auto()
    DECODE_ERROR = auto()
    CANCELLED = auto()
    SCREENSHOT_FAILED = auto()


@dataclass
class ScanResult:
    outcome: ScanOutcome
    text: str | None = None
    all_texts: tuple[str, ...] = ()
    copied: bool = False
    otp_fields: OtpFields | None = None


_STATUS_MESSAGES = {
    ScanOutcome.SUCCESS: "QR code detected",
    ScanOutcome.MULTIPLE: "Multiple QR codes detected — choose one",
    ScanOutcome.NOT_FOUND: "No QR code detected",
    ScanOutcome.EMPTY_PAYLOAD: "QR code found but it is empty",
    ScanOutcome.INVALID_IMAGE: "Unable to decode QR code",
    ScanOutcome.DECODE_ERROR: "Unable to decode QR code",
    ScanOutcome.CANCELLED: "Scan cancelled",
    ScanOutcome.SCREENSHOT_FAILED: "Screenshot could not be captured",
}


def status_message(outcome: ScanOutcome) -> str:
    return _STATUS_MESSAGES[outcome]


def run_scan(display: Gdk.Display, config: Config) -> ScanResult:
    """Run one full scan cycle synchronously (the portal call itself runs a
    nested GLib main loop internally while the user makes a selection)."""
    try:
        image = take_interactive_screenshot()
    except ScreenshotCancelled:
        return ScanResult(outcome=ScanOutcome.CANCELLED)
    except ScreenshotError:
        return ScanResult(outcome=ScanOutcome.SCREENSHOT_FAILED)

    decode_result = decode_qr(image.data)
    # Drop our reference to the image bytes as soon as decoding is done.
    del image

    if decode_result.status == DecodeStatus.NOT_FOUND:
        return ScanResult(outcome=ScanOutcome.NOT_FOUND)
    if decode_result.status == DecodeStatus.INVALID_IMAGE:
        return ScanResult(outcome=ScanOutcome.INVALID_IMAGE)
    if decode_result.status == DecodeStatus.DECODE_ERROR:
        return ScanResult(outcome=ScanOutcome.DECODE_ERROR)
    if decode_result.status == DecodeStatus.EMPTY_PAYLOAD:
        return ScanResult(outcome=ScanOutcome.EMPTY_PAYLOAD)
    if decode_result.status == DecodeStatus.MULTIPLE_FOUND:
        return ScanResult(
            outcome=ScanOutcome.MULTIPLE, all_texts=decode_result.all_texts
        )

    # SUCCESS
    text = decode_result.text
    copied = False
    if config.auto_copy and text is not None:
        copied = clipboard_mod.copy_text(display, text)
        if copied and config.clipboard_clear_seconds > 0:
            clipboard_mod.schedule_clear(
                display, config.clipboard_clear_seconds, text
            )

    otp_fields = parse_otpauth(text) if text is not None else None

    return ScanResult(
        outcome=ScanOutcome.SUCCESS, text=text, copied=copied, otp_fields=otp_fields
    )


def send_notification(app: Gio.Application, title: str, body: str) -> None:
    """Send a small, non-sensitive desktop notification. `body` must never
    contain QR content — only fixed, generic strings are passed by callers."""
    notification = Gio.Notification.new(title)
    notification.set_body(body)
    app.send_notification(None, notification)
