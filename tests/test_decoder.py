"""Decoder tests. Generates QR fixtures in-memory with `qrcode` and verifies
that qr_text_reader.decoder returns the payload byte-for-byte unchanged."""

from __future__ import annotations

import io

import pytest
import qrcode

from qr_text_reader.decoder import DecodeStatus, decode_qr


def _make_qr_png_bytes(text: str) -> bytes:
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.parametrize(
    "payload",
    [
        "hello world",  # 1. simple text
        "https://example.com/test?a=1&b=2",  # 2. URL with query params
        "otpauth://totp/Test:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Test",  # 3. otpauth
        "Merhaba dünya, çşğüöİ ĞÜŞ",  # 4. Turkish characters
        "A" * 800,  # 5. long text
    ],
)
def test_decode_preserves_raw_text_exactly(payload: str):
    png_bytes = _make_qr_png_bytes(payload)
    result = decode_qr(png_bytes)
    assert result.status == DecodeStatus.OK
    assert result.text == payload  # byte-for-byte, no transformation


def test_otpauth_url_is_not_parsed_or_split():
    payload = "otpauth://totp/Example:user@example.com?secret=ABCDEF123456&issuer=Example"
    png_bytes = _make_qr_png_bytes(payload)
    result = decode_qr(png_bytes)
    assert result.status == DecodeStatus.OK
    # Must remain a single opaque string — not a dict, not a tuple of fields.
    assert isinstance(result.text, str)
    assert result.text == payload
    assert "secret=ABCDEF123456" in result.text  # untouched substring


def test_no_qr_in_image_returns_not_found():
    # A plain solid image with no QR code encoded in it.
    from PIL import Image

    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    result = decode_qr(buf.getvalue())
    assert result.status == DecodeStatus.NOT_FOUND
    assert result.text is None


def test_corrupted_image_bytes_do_not_crash():
    garbage = b"this is not a valid image file at all"
    result = decode_qr(garbage)
    assert result.status == DecodeStatus.INVALID_IMAGE
    assert result.text is None


def test_multiple_qr_codes_are_all_returned_not_merged():
    # Build one image containing two distinct QR codes side by side.
    from PIL import Image

    payload_a = "AAA-first-code"
    payload_b = "BBB-second-code"
    img_a = qrcode.make(payload_a).convert("RGB")
    img_b = qrcode.make(payload_b).convert("RGB")

    width = img_a.width + img_b.width
    height = max(img_a.height, img_b.height)
    combined = Image.new("RGB", (width, height), color="white")
    combined.paste(img_a, (0, 0))
    combined.paste(img_b, (img_a.width, 0))

    buf = io.BytesIO()
    combined.save(buf, format="PNG")

    result = decode_qr(buf.getvalue())
    assert result.status == DecodeStatus.MULTIPLE_FOUND
    assert result.candidate_count == 2
    assert payload_a in result.all_texts
    assert payload_b in result.all_texts
