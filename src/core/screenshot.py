from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal as Signal

from app.screenshot_overlay import ScreenshotOverlay
from utils.logger import get_logger

logger = get_logger("screenshot")


class ScreenshotCapture(QObject):
    """High-level coordinator for triggering a screenshot capture.

    Creates a :class:`ScreenshotOverlay` lazily on first use and forwards its
    signals to callers.  The overlay is re-used across captures; its internal
    state is reset each time :meth:`start_capture` is called.
    """

    capture_complete = Signal(bytes)
    capture_cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlay: ScreenshotOverlay | None = None
        logger.debug("ScreenshotCapture initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_capture(self) -> None:
        """Show the selection overlay and begin a capture session."""
        overlay = self._get_overlay()
        overlay.start()
        logger.debug("Capture session started")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_overlay(self) -> ScreenshotOverlay:
        """Return the cached overlay, creating it on first call."""
        if self._overlay is None:
            self._overlay = ScreenshotOverlay()
            self._overlay.capture_complete.connect(self._on_capture_complete)
            self._overlay.capture_cancelled.connect(self._on_capture_cancelled)
            logger.debug("ScreenshotOverlay created and signals connected")
        return self._overlay

    def _on_capture_complete(self, png_bytes: bytes) -> None:
        logger.debug("Forwarding capture_complete (%d bytes)", len(png_bytes))
        self.capture_complete.emit(png_bytes)

    def _on_capture_cancelled(self) -> None:
        logger.debug("Forwarding capture_cancelled")
        self.capture_cancelled.emit()
