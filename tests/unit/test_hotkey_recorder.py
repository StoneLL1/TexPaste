from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from PyQt6.QtWidgets import QApplication

from app.hotkey_recorder import HotkeyRecorder


@pytest.fixture
def qapp() -> QApplication:
    """Ensure QApplication exists for Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_hotkey_recorder_initial_state(qapp: QApplication) -> None:
    """Recorder starts with empty hotkey and 'Click to record' placeholder."""
    recorder = HotkeyRecorder()
    assert recorder.hotkey() == ""
    assert recorder.placeholderText() == "点击录制快捷键..."


def test_hotkey_recorder_set_hotkey(qapp: QApplication) -> None:
    """setHotkey updates the displayed text."""
    recorder = HotkeyRecorder()
    recorder.setHotkey("ctrl+shift+a")
    assert recorder.hotkey() == "ctrl+shift+a"
    assert recorder.text() == "ctrl+shift+a"


def test_hotkey_recorder_clear_hotkey(qapp: QApplication) -> None:
    """clearHotkey resets to empty state."""
    recorder = HotkeyRecorder()
    recorder.setHotkey("ctrl+shift+a")
    recorder.clearHotkey()
    assert recorder.hotkey() == ""
    assert recorder.text() == ""
