"""Clipboard tests using lightweight fakes instead of a real Gdk.Display,
so the suite can run headless (e.g. in CI without a Wayland/X session).
"""

from __future__ import annotations

from qr_text_reader import clipboard


class _FakeClipboard:
    def __init__(self):
        self.set_calls: list[str] = []

    def set(self, text: str) -> None:
        self.set_calls.append(text)


class _FakeDisplay:
    def __init__(self):
        self._clipboard = _FakeClipboard()

    def get_clipboard(self):
        return self._clipboard


def test_copy_text_writes_to_clipboard():
    display = _FakeDisplay()
    ok = clipboard.copy_text(display, "hello-clipboard-payload")
    assert ok is True
    assert display._clipboard.set_calls == ["hello-clipboard-payload"]


def test_copy_text_does_not_swallow_exceptions_silently(monkeypatch):
    class _BrokenClipboard:
        def set(self, text):
            raise RuntimeError("simulated backend failure")

    class _BrokenDisplay:
        def get_clipboard(self):
            return _BrokenClipboard()

    # copy_text only catches GLib.Error per its contract; a RuntimeError here
    # documents that unexpected non-GLib errors are NOT silently hidden as
    # "success" — this test intentionally expects it to propagate.
    import pytest

    with pytest.raises(RuntimeError):
        clipboard.copy_text(_BrokenDisplay(), "x")


def test_schedule_clear_returns_none_when_disabled():
    display = _FakeDisplay()
    source_id = clipboard.schedule_clear(display, seconds=0, expected_text="x")
    assert source_id is None
