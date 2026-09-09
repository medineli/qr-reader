"""Minimal MVP configuration.

Deliberately small: only the settings that materially affect behavior.
Stored as plain JSON under $XDG_CONFIG_HOME (never contains QR content).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .security import Event, log_error


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(base) / "qr-text-reader"


def _config_path() -> Path:
    return _config_dir() / "config.json"


@dataclass
class Config:
    auto_copy: bool = True
    show_notification: bool = True
    # 0 = never auto-clear clipboard. Any positive int = seconds.
    clipboard_clear_seconds: int = 0

    @classmethod
    def load(cls) -> "Config":
        path = _config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
            return cls(**known)
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            log_error(Event.TEMP_FILE_CLEANUP_FAILED, exc)  # generic technical log
            return cls()

    def save(self) -> None:
        d = _config_dir()
        d.mkdir(parents=True, exist_ok=True)
        _config_path().write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
