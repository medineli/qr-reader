"""Security tests:
1. QR content never appears in log output.
2. No networking modules/functions are used anywhere in the source tree.
3. Screenshot temp files are removed after processing.
"""

from __future__ import annotations

import ast
import io
import logging
import re
from pathlib import Path

import qrcode

from qr_text_reader.decoder import decode_qr
from qr_text_reader.security import get_logger

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "qr_text_reader"

FORBIDDEN_NETWORK_IMPORTS = {
    "socket",
    "requests",
    "urllib.request",
    "http.client",
    "httpx",
    "aiohttp",
    "ftplib",
    "smtplib",
}


def _sensitive_secret_marker() -> str:
    return "SECRET_MARKER_XJ9QZ_MUST_NEVER_APPEAR_IN_LOGS"


def test_decoded_qr_content_never_appears_in_logs(caplog):
    secret_text = f"otpauth://totp/Test:user@example.com?secret={_sensitive_secret_marker()}"
    img = qrcode.make(secret_text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    logger = get_logger()
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        result = decode_qr(buf.getvalue())

    assert result.text == secret_text  # sanity: it really was decoded
    for record in caplog.records:
        assert _sensitive_secret_marker() not in record.getMessage()
        assert secret_text not in record.getMessage()


def test_no_networking_imports_anywhere_in_source():
    offending: list[str] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_NETWORK_IMPORTS:
                        offending.append(f"{py_file}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module in FORBIDDEN_NETWORK_IMPORTS:
                    offending.append(f"{py_file}: from {node.module} import ...")
    assert not offending, f"Forbidden networking imports found: {offending}"


def test_no_shell_execution_of_dynamic_data():
    """QR content must never be passed to subprocess/os.system/eval/exec."""
    dangerous_calls = {"system", "popen", "eval", "exec"}
    offending: list[str] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name in dangerous_calls:
                    offending.append(f"{py_file}:{node.lineno}: call to {name}()")
        # subprocess module must not appear at all in this project
        if re.search(r"\bimport subprocess\b|\bfrom subprocess\b", source):
            offending.append(f"{py_file}: imports subprocess")
    assert not offending, f"Dangerous execution calls found: {offending}"


def test_screenshot_temp_file_is_removed_after_read(tmp_path):
    from qr_text_reader.security import secure_delete

    f = tmp_path / "qr_capture.png"
    f.write_bytes(b"fake-png-bytes")
    assert f.exists()
    secure_delete(f)
    assert not f.exists()
