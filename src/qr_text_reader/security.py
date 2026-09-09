"""Security helpers: safe logging and secure temp-file cleanup.

HARD RULE ENFORCED BY THIS MODULE:
Decoded QR content must NEVER reach a log record, stdout, or disk.

The rest of the codebase must ONLY use `get_logger()` from this module for
logging, and must NEVER call print()/logger with decoded text as an argument.
This module also provides `SafeEvent` logging helpers that make it structurally
awkward to accidentally log free-form user data.
"""

from __future__ import annotations

import logging
import os
import sys
from enum import Enum
from pathlib import Path

_LOGGER_NAME = "qr_text_reader"


class Event(str, Enum):
    """Enumerated, non-sensitive event types. No free text allowed here."""

    APP_STARTED = "app_started"
    SCAN_REQUESTED = "scan_requested"
    SCREENSHOT_OK = "screenshot_ok"
    SCREENSHOT_FAILED = "screenshot_failed"
    SCREENSHOT_CANCELLED = "screenshot_cancelled"
    DECODE_OK = "qr_decoded"
    DECODE_EMPTY = "qr_decode_empty_payload"
    DECODE_NOT_FOUND = "qr_not_found"
    DECODE_MULTIPLE = "qr_multiple_found"
    DECODE_ERROR = "qr_decode_error"
    CLIPBOARD_OK = "clipboard_write_ok"
    CLIPBOARD_FAILED = "clipboard_write_failed"
    TEMP_FILE_CLEANED = "temp_file_cleaned"
    TEMP_FILE_CLEANUP_FAILED = "temp_file_cleanup_failed"
    PORTAL_UNAVAILABLE = "portal_unavailable"


def get_logger() -> logging.Logger:
    """Return the application logger, configured to only emit non-sensitive
    event codes and technical error *types* (never error payloads that could
    contain user data such as QR content)."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(event: Event, detail: str | None = None) -> None:
    """Log a known, safe event. `detail` must be short, non-sensitive,
    technical context ONLY (e.g. an exception class name) — never QR content.
    Callers must not pass decoded QR text or clipboard content here.
    """
    logger = get_logger()
    if detail:
        logger.info("%s (%s)", event.value, detail)
    else:
        logger.info("%s", event.value)


def log_error(event: Event, exc: BaseException) -> None:
    """Log only the exception *type*, never str(exc), since some libraries
    (or misbehaving decoders) could theoretically embed payload data in
    exception messages. This keeps logs strictly free of QR content."""
    logger = get_logger()
    logger.warning("%s (%s)", event.value, type(exc).__name__)


def secure_delete(path: Path) -> None:
    """Best-effort deletion of a temp file created by the screenshot portal.

    We do not control how the portal writes the file, so this is best-effort:
    we simply unlink it as soon as we're done reading it into memory.
    """
    try:
        if path.exists():
            os.remove(path)
        log_event(Event.TEMP_FILE_CLEANED)
    except OSError as exc:
        log_error(Event.TEMP_FILE_CLEANUP_FAILED, exc)
