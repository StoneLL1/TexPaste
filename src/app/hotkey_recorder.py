from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from PyQt6.QtWidgets import QLineEdit

from utils.logger import get_logger

logger = get_logger(__name__)

_MODIFIER_KEYS: frozenset[int] = frozenset(
    {
        Qt.Key.Key_Control,
        Qt.Key.Key_Shift,
        Qt.Key.Key_Alt,
        Qt.Key.Key_Meta,
    }
)

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

    User clicks the field -> types key combination -> field displays the combo.
    """

    hotkeyChanged = pyqtSignal(str)  # Emitted when hotkey changes

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
        if hotkey:
            self.hotkeyChanged.emit(hotkey)

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
            self.hotkeyChanged.emit(self._recorded_hotkey)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """Clear keys when released."""
        key = event.key()
        self._current_keys.discard(key)
        # Don't clear text on release - keep showing recorded combo

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
                # Regular key - get its name
                key_name = Qt.Key(key).name.lower()
                # Handle single letter keys (Key_A -> 'a')
                if key_name.startswith("key_"):
                    key_name = key_name[4:]
                regular_key = key_name

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
