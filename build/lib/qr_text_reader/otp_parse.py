"""Parses `otpauth://` QR payloads to surface the `secret` and
`issuer`/account fields separately, for convenience.

IMPORTANT: This module only READS structure out of a string the user already
has in front of them (it's already fully visible as raw text elsewhere in
the UI) — it does not fetch, transform, or generate anything (no TOTP codes
are computed). No network. No logging of the parsed values themselves.

If the payload is not a well-formed `otpauth://` URI, `is_otpauth` is False
and `secret`/`issuer`/`account` are all None — the raw text view remains the
only representation, unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

from .security import Event, log_event


@dataclass
class OtpFields:
    is_otpauth: bool = False
    secret: str | None = None
    issuer: str | None = None
    account: str | None = None


def parse_otpauth(raw_text: str) -> OtpFields:
    if not raw_text.startswith("otpauth://"):
        return OtpFields(is_otpauth=False)

    try:
        parsed = urlparse(raw_text)
    except ValueError:
        return OtpFields(is_otpauth=False)

    if parsed.scheme != "otpauth" or not parsed.netloc:
        return OtpFields(is_otpauth=False)

    query = parse_qs(parsed.query)
    secret = query.get("secret", [None])[0]
    issuer_param = query.get("issuer", [None])[0]

    label = unquote(parsed.path.lstrip("/"))
    if ":" in label:
        label_issuer, _, account = label.partition(":")
    else:
        label_issuer, account = None, label

    issuer = issuer_param or label_issuer or None
    account = account or None

    result = OtpFields(
        is_otpauth=True,
        secret=secret,
        issuer=issuer,
        account=account,
    )
    # Only log that parsing happened and which fields were present — never
    # the field values themselves.
    log_event(
        Event.DECODE_OK,
        detail=f"otp_fields_present secret={secret is not None} issuer={issuer is not None}",
    )
    return result
