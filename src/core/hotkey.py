from __future__ import annotations

import threading
from typing import Optional

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal as Signal

from utils.logger import get_logger

logger = get_logger(__name__)

# Multi-char modifier keys that must be wrapped in angle brackets for pynput GlobalHotKeys
_MODIFIER_KEYS: frozenset[str] = frozenset(
    {"ctrl", "shift", "alt", "win", "cmd", "meta", "super"}
)


def _convert_key_string(key_str: str) -> str:
    """Convert a human-readable key string to pynput GlobalHotKeys format.

    Example: ``"ctrl+shift+a"`` → ``"<ctrl>+<shift>+a"``

    Args:
        key_str: Key combination string using ``+`` as separator,
                 e.g. ``"ctrl+shift+a"``.

    Returns:
        Key string in pynput GlobalHotKeys format.
    """
    parts = key_str.lower().strip().split("+")
    converted: list[str] = []
    for part in parts:
        part = part.strip()
        if part in _MODIFIER_KEYS or len(part) > 1:
            converted.append(f"<{part}>")
        else:
            converted.append(part)
    return "+".join(converted)


class HotkeyManager(QObject):
    """Global hotkey listener backed by a pynput ``GlobalHotKeys`` daemon thread.

    Signals are emitted from the pynput background thread; Qt's signal/slot
    mechanism handles cross-thread queuing automatically.
    """

    screenshot_triggered: Signal = Signal()
    paste_triggered: Signal = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, screenshot_key: str, paste_key: str) -> bool:
        """Parse key strings and start the pynput listener in a daemon thread.

        Args:
            screenshot_key: Key combo for screenshot, e.g. ``"ctrl+shift+a"``.
            paste_key: Key combo for smart paste, e.g. ``"ctrl+shift+v"``.

        Returns:
            ``True`` if the listener started successfully, ``False`` otherwise.
        """
        with self._lock:
            if self._listener is not None:
                logger.warning("HotkeyManager.register called while listener is active; stopping first.")
                self._stop_listener()

            pynput_screenshot = _convert_key_string(screenshot_key)
            pynput_paste = _convert_key_string(paste_key)

            logger.info(
                "Registering hotkeys — screenshot: %s → %s, paste: %s → %s",
                screenshot_key,
                pynput_screenshot,
                paste_key,
                pynput_paste,
            )

            hotkeys: dict[str, object] = {
                pynput_screenshot: self._on_screenshot,
                pynput_paste: self._on_paste,
            }

            try:
                self._listener = keyboard.GlobalHotKeys(hotkeys)
                self._thread = threading.Thread(
                    target=self._listener.run,
                    name="HotkeyListenerThread",
                    daemon=True,
                )
                self._thread.start()
                logger.info("HotkeyManager: listener thread started.")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.error("HotkeyManager: failed to start listener — %s", exc)
                self._listener = None
                self._thread = None
                return False

    def unregister(self) -> None:
        """Stop the pynput listener thread."""
        with self._lock:
            self._stop_listener()

    def update_hotkeys(self, screenshot_key: str, paste_key: str) -> bool:
        """Unregister any existing listener, then register new hotkeys.

        Args:
            screenshot_key: New screenshot key combo.
            paste_key: New smart-paste key combo.

        Returns:
            ``True`` if the new listener started successfully.
        """
        self.unregister()
        return self.register(screenshot_key, paste_key)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _stop_listener(self) -> None:
        """Stop the listener. Must be called with ``_lock`` held."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:  # noqa: BLE001
                logger.warning("HotkeyManager: error while stopping listener — %s", exc)
            self._listener = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning("HotkeyManager: listener thread did not stop within 2 s.")
            self._thread = None

        logger.info("HotkeyManager: listener stopped.")

    def _on_screenshot(self) -> None:
        """Pynput callback — emits :attr:`screenshot_triggered`."""
        logger.debug("HotkeyManager: screenshot hotkey activated.")
        self.screenshot_triggered.emit()

    def _on_paste(self) -> None:
        """Pynput callback — emits :attr:`paste_triggered`."""
        logger.debug("HotkeyManager: paste hotkey activated.")
        self.paste_triggered.emit()
