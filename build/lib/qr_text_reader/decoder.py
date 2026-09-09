"""QR decoding. Returns the RAW payload string, unmodified.

This module MUST NOT:
- URL-decode, base64-decode, or otherwise transform the payload.
- Split the payload into fields (e.g. otpauth query params).
- Log the payload.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum, auto

from PIL import Image
from pyzbar import pyzbar

from .security import Event, log_error, log_event


class DecodeStatus(Enum):
    OK = auto()
    NOT_FOUND = auto()
    MULTIPLE_FOUND = auto()
    EMPTY_PAYLOAD = auto()
    INVALID_IMAGE = auto()
    DECODE_ERROR = auto()


@dataclass
class DecodeResult:
    status: DecodeStatus
    text: str | None = None
    candidate_count: int = 0
    # If MULTIPLE_FOUND, all raw texts are offered so the user can pick —
    # we never silently choose one for them, and we never merge them.
    all_texts: tuple[str, ...] = ()


def decode_qr(image_bytes: bytes) -> DecodeResult:
    """Decode QR code(s) from raw image bytes held in memory.

    No file I/O happens here. `image_bytes` and any intermediate PIL image
    are only referenced for the duration of this call.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001 - Pillow raises various error types
        log_error(Event.DECODE_ERROR, exc)
        return DecodeResult(status=DecodeStatus.INVALID_IMAGE)

    try:
        symbols = pyzbar.decode(image)
    except Exception as exc:  # noqa: BLE001 - underlying zbar can raise various types
        log_error(Event.DECODE_ERROR, exc)
        return DecodeResult(status=DecodeStatus.DECODE_ERROR)
    finally:
        image.close()

    # Only consider QRCODE symbol type; ignore barcodes etc. to avoid
    # surprising the user with non-QR decodes.
    qr_symbols = [s for s in symbols if s.type == "QRCODE"]

    if not qr_symbols:
        log_event(Event.DECODE_NOT_FOUND)
        return DecodeResult(status=DecodeStatus.NOT_FOUND)

    texts = tuple(sym.data.decode("utf-8", errors="strict") for sym in qr_symbols)

    if len(texts) > 1:
        log_event(Event.DECODE_MULTIPLE)
        return DecodeResult(
            status=DecodeStatus.MULTIPLE_FOUND,
            candidate_count=len(texts),
            all_texts=texts,
        )

    raw_text = texts[0]
    if raw_text == "":
        log_event(Event.DECODE_EMPTY)
        return DecodeResult(status=DecodeStatus.EMPTY_PAYLOAD)

    log_event(Event.DECODE_OK)
    return DecodeResult(status=DecodeStatus.OK, text=raw_text, candidate_count=1)
