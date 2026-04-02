# UI Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multimodal model hint in API config page and implement hotkey recording feature

**Architecture:** 
- API Tab: Add a styled hint label below model combo to inform users about multimodal requirement
- Hotkeys Tab: Replace QLineEdit with a custom HotkeyRecorder widget that captures keyboard input in real-time

**Tech Stack:** PyQt6, pynput (existing), QKeyEvent handling

---

## File Structure

| File | Responsibility |
|------|----------------|
| `src/app/settings_ui.py` | Main settings dialog - modify API tab hint, replace hotkey inputs |
| `src/app/hotkey_recorder.py` | **NEW** - Custom widget for recording hotkey combinations |
| `tests/unit/test_hotkey_recorder.py` | **NEW** - Unit tests for HotkeyRecorder |

---

## Task 1: Add Multimodal Model Hint in API Tab

**Files:**
- Modify: `src/app/settings_ui.py:414-417` (after model combo row)

- [ ] **Step 1: Add hint label below model combo**

In `_build_api_tab()` method, after the model combo row (line 417), add:

```python
# Model hint - inform user about multimodal requirement
model_hint = QLabel("💡 请配置支持图像输入的多模态大模型（如 GPT-4o、Claude Vision）")
model_hint.setStyleSheet("color: #666666; font-size: 11px; padding-left: 4px;")
model_hint.setWordWrap(True)
form.addRow("", model_hint)
```

- [ ] **Step 2: Run tests to verify no regressions**

Run: `pytest tests/unit/ -v`
Expected: All tests pass

- [ ] **Step 3: Manual verification**

Run: `python src/main.py`
Expected: Settings → API 配置 → Model 下方显示灰色提示文字

- [ ] **Step 4: Commit**

```bash
git add src/app/settings_ui.py
git commit -m "feat(ui): add multimodal model hint in API config tab"
```

---

## Task 2: Create HotkeyRecorder Widget

**Files:**
- Create: `src/app/hotkey_recorder.py`
- Create: `tests/unit/test_hotkey_recorder.py`

- [ ] **Step 1: Write the failing test for HotkeyRecorder initialization**

```python
# tests/unit/test_hotkey_recorder.py
from __future__ import annotations

import pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_hotkey_recorder.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.hotkey_recorder'"

- [ ] **Step 3: Write minimal HotkeyRecorder implementation**

```python
# src/app/hotkey_recorder.py
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QLineEdit

from utils.logger import get_logger

logger = get_logger(__name__)

_MODIFIER_KEYS: frozenset[int] = frozenset({
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
})

_KEY_NAMES: dict[int, str] = {
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Meta: "win",
}


class HotkeyRecorder(QLineEdit):
    """A QLineEdit that captures keyboard combinations when focused.

    Usage:
        recorder = HotkeyRecorder()
        recorder.hotkeyChanged.connect(lambda key: print(f"Recorded: {key}"))

    User clicks the field → types key combination → field displays the combo.
    """

    def __init__(self, parent: None = None) -> None:
        super().__init__(parent)
        self._current_keys: set[int] = set()
        self._recorded_hotkey: str = ""
        self.setPlaceholderText("点击录制快捷键...")
        self.setReadOnly(True)  # Prevent direct text editing
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def hotkey(self) -> str:
        """Return the currently recorded hotkey string."""
        return self._recorded_hotkey

    def setHotkey(self, hotkey: str) -> None:
        """Set hotkey programmatically (e.g., loading from config)."""
        self._recorded_hotkey = hotkey
        self.setText(hotkey)

    def clearHotkey(self) -> None:
        """Clear the recorded hotkey."""
        self._recorded_hotkey = ""
        self._current_keys.clear()
        self.setText("")
        self.setPlaceholderText("点击录制快捷键...")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Capture key presses and build hotkey string."""
        key = event.key()

        # Skip modifier-only presses (they're tracked in _current_keys)
        if key in _MODIFIER_KEYS:
            self._current_keys.add(key)
            self._update_display()
            return

        # Regular key pressed with modifiers
        self._current_keys.add(key)
        self._update_display()

        # Finalize the hotkey when a non-modifier key is pressed
        if key not in _MODIFIER_KEYS:
            self._recorded_hotkey = self._build_hotkey_string()
            logger.info("Hotkey recorded: %s", self._recorded_hotkey)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Clear keys when released."""
        key = event.key()
        if key in _MODIFIER_KEYS:
            self._current_keys.discard(key)
        # Don't clear the text on release - keep showing the recorded combo

    def _update_display(self) -> None:
        """Update the text field to show current key combination."""
        self.setText(self._build_hotkey_string())

    def _build_hotkey_string(self) -> str:
        """Convert current key set to human-readable string."""
        if not self._current_keys:
            return ""

        modifiers: list[str] = []
        regular_key: str = ""

        for key in self._current_keys:
            if key in _KEY_NAMES:
                modifiers.append(_KEY_NAMES[key])
            elif key == Qt.Key.Key_unknown:
                continue
            else:
                # Regular key - get its text representation
                regular_key = Qt.Key(key).name.lower()

        # Sort modifiers in consistent order
        modifier_order = ["ctrl", "shift", "alt", "win"]
        sorted_modifiers = [m for m in modifier_order if m in modifiers]

        if sorted_modifiers and regular_key:
            return "+".join(sorted_modifiers + [regular_key])
        elif sorted_modifiers:
            return "+".join(sorted_modifiers)
        elif regular_key:
            return regular_key
        return ""

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Clear previous recording when user clicks to record new."""
        super().focusInEvent(event)
        self._current_keys.clear()
        self.setText("")
        self.setPlaceholderText("按下快捷键组合...")

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Restore display when focus leaves."""
        super().focusOutEvent(event)
        if self._recorded_hotkey:
            self.setText(self._recorded_hotkey)
        else:
            self.setText("")
            self.setPlaceholderText("点击录制快捷键...")
```

- [ ] **Step 4: Fix import issue in test**

```python
# tests/unit/test_hotkey_recorder.py - fix import path
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
if src_path not in sys.path:
    sys.path.insert(0, str(src_path))

from app.hotkey_recorder import HotkeyRecorder
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_hotkey_recorder.py -v`
Expected: PASS

- [ ] **Step 6: Write test for setHotkey method**

```python
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
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/unit/test_hotkey_recorder.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/app/hotkey_recorder.py tests/unit/test_hotkey_recorder.py
git commit -m "feat(ui): add HotkeyRecorder widget for keyboard capture"
```

---

## Task 3: Integrate HotkeyRecorder into Settings UI

**Files:**
- Modify: `src/app/settings_ui.py:486-518` (hotkeys tab section)
- Modify: `src/app/settings_ui.py:1-32` (imports)

- [ ] **Step 1: Add import for HotkeyRecorder**

At the top of `src/app/settings_ui.py`, add import after line 32:

```python
from app.hotkey_recorder import HotkeyRecorder
```

- [ ] **Step 2: Replace QLineEdit with HotkeyRecorder in _build_hotkeys_tab**

Replace lines 495-503:

```python
# OLD CODE (remove):
self._screenshot_key_edit = QLineEdit()
self._screenshot_key_edit.setPlaceholderText("ctrl+shift+a")
form.addRow("截图快捷键", self._screenshot_key_edit)

self._paste_key_edit = QLineEdit()
self._paste_key_edit.setPlaceholderText("ctrl+shift+v")
form.addRow("粘贴快捷键", self._paste_key_edit)

# NEW CODE (replace with):
self._screenshot_key_recorder = HotkeyRecorder()
form.addRow("截图快捷键", self._screenshot_key_recorder)

self._paste_key_recorder = HotkeyRecorder()
form.addRow("粘贴快捷键", self._paste_key_recorder)
```

- [ ] **Step 3: Update hint label**

Replace line 506-508:

```python
# OLD CODE:
hint_label = QLabel("格式：ctrl+shift+a，可使用 ctrl/shift/alt/win")
hint_label.setStyleSheet("color: gray; font-size: 11px;")
form.addRow("", hint_label)

# NEW CODE:
hint_label = QLabel("点击输入框后按下快捷键组合即可自动录制")
hint_label.setStyleSheet("color: #666666; font-size: 11px;")
form.addRow("", hint_label)
```

- [ ] **Step 4: Update _reset_hotkeys method**

Replace lines 865-868:

```python
# OLD CODE:
def _reset_hotkeys(self) -> None:
    """Restore screenshot and paste hotkeys to factory defaults."""
    self._screenshot_key_edit.setText("ctrl+shift+a")
    self._paste_key_edit.setText("ctrl+shift+v")

# NEW CODE:
def _reset_hotkeys(self) -> None:
    """Restore screenshot and paste hotkeys to factory defaults."""
    self._screenshot_key_recorder.setHotkey("ctrl+shift+a")
    self._paste_key_recorder.setHotkey("ctrl+shift+v")
```

- [ ] **Step 5: Update _load_settings method**

Replace lines 805-806:

```python
# OLD CODE:
self._screenshot_key_edit.setText(self._config.get("hotkeys.screenshot", "ctrl+shift+a"))
self._paste_key_edit.setText(self._config.get("hotkeys.paste", "ctrl+shift+v"))

# NEW CODE:
self._screenshot_key_recorder.setHotkey(self._config.get("hotkeys.screenshot", "ctrl+shift+a"))
self._paste_key_recorder.setHotkey(self._config.get("hotkeys.paste", "ctrl+shift+v"))
```

- [ ] **Step 6: Update _save_settings method**

Replace lines 837-838:

```python
# OLD CODE:
self._config.set("hotkeys.screenshot", self._screenshot_key_edit.text().strip())
self._config.set("hotkeys.paste", self._paste_key_edit.text().strip())

# NEW CODE:
self._config.set("hotkeys.screenshot", self._screenshot_key_recorder.hotkey())
self._config.set("hotkeys.paste", self._paste_key_recorder.hotkey())
```

- [ ] **Step 7: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests pass

- [ ] **Step 8: Manual verification**

Run: `python src/main.py`
Expected:
1. Settings → 快捷键 Tab shows two "Click to record" fields
2. Click field → press ctrl+shift+a → field shows "ctrl+shift+a"
3. Click "恢复默认" → fields show default hotkeys
4. Save and reopen → hotkeys are preserved

- [ ] **Step 9: Commit**

```bash
git add src/app/settings_ui.py
git commit -m "feat(ui): integrate HotkeyRecorder into settings hotkeys tab"
```

---

## Task 4: Add QFocusEvent Import Fix

**Files:**
- Modify: `src/app/hotkey_recorder.py:6` (imports)

- [ ] **Step 1: Add missing QFocusEvent import**

Add to imports in `hotkey_recorder.py`:

```python
from PyQt6.QtGui import QFocusEvent, QKeyEvent
```

- [ ] **Step 2: Run ruff check**

Run: `ruff check src/app/hotkey_recorder.py`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/app/hotkey_recorder.py
git commit -m "fix: add missing QFocusEvent import"
```

---

## Task 5: Final Integration Test and Cleanup

**Files:**
- Run full test suite

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run ruff lint and format**

Run: `ruff check src/ && ruff format src/`
Expected: All checks pass

- [ ] **Step 3: Run mypy type check**

Run: `mypy src/app/hotkey_recorder.py`
Expected: No errors

- [ ] **Step 4: Manual end-to-end test**

Run: `python src/main.py`
Verify:
1. Settings → API 配置 → Model 下显示多模态提示
2. Settings → 快捷键 → 点击录制 → 按键组合显示正确
3. 保存设置 → 重开应用 → 设置保留

- [ ] **Step 5: Push to GitHub**

```bash
git push origin main
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] API配置页面大模型名称下面有提示 → Task 1
- [x] 快捷键改成可录制的形式 → Task 2, Task 3

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later" in plan ✅
- All code blocks have complete implementations ✅

**3. Type consistency:**
- HotkeyRecorder.hotkey() returns str ✅
- HotkeyRecorder.setHotkey(hotkey: str) ✅
- All method signatures match between tasks ✅