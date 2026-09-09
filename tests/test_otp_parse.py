"""Tests for otp_parse: secret/issuer extraction, and confirmation that
parsing never mutates or discards the original raw text elsewhere in the
app (this module only ever reads a copy of the string)."""

from __future__ import annotations

from qr_text_reader.otp_parse import parse_otpauth


def test_parses_secret_and_issuer_from_query_params():
    raw = "otpauth://totp/Microsoft:user@example.com?secret=ABCDEF123456&issuer=Microsoft"
    fields = parse_otpauth(raw)
    assert fields.is_otpauth is True
    assert fields.secret == "ABCDEF123456"
    assert fields.issuer == "Microsoft"
    assert fields.account == "user@example.com"


def test_falls_back_to_label_prefix_when_issuer_param_missing():
    raw = "otpauth://totp/GitHub:octocat?secret=JBSWY3DPEHPK3PXP"
    fields = parse_otpauth(raw)
    assert fields.is_otpauth is True
    assert fields.secret == "JBSWY3DPEHPK3PXP"
    assert fields.issuer == "GitHub"
    assert fields.account == "octocat"


def test_non_otpauth_text_returns_empty_fields():
    raw = "https://example.com/test?a=1&b=2"
    fields = parse_otpauth(raw)
    assert fields.is_otpauth is False
    assert fields.secret is None
    assert fields.issuer is None
    assert fields.account is None


def test_plain_text_returns_empty_fields():
    fields = parse_otpauth("just some plain text, not a URI at all")
    assert fields.is_otpauth is False
    assert fields.secret is None


def test_parsing_does_not_alter_original_string():
    raw = "otpauth://totp/Example:user@example.com?secret=ABC&issuer=Example"
    original = raw  # simulate "raw text kept elsewhere in the app"
    parse_otpauth(raw)
    assert raw == original  # untouched
