from __future__ import annotations

from PyQt6.QtCore import QBuffer, QByteArray, QPoint, QRect, Qt, pyqtSignal as Signal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QRubberBand, QWidget

from utils.logger import get_logger

logger = get_logger("screenshot_overlay")


class ScreenshotOverlay(QWidget):
    """Full-screen transparent overlay for region selection and capture."""

    capture_complete = Signal(bytes)
    capture_cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._origin: QPoint = QPoint()
        self._selection: QRect = QRect()
        self._rubber_band: QRubberBand = QRubberBand(QRubberBand.Shape.Rectangle, self)

        logger.debug("ScreenshotOverlay initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Show the overlay covering the entire primary screen."""
        self._selection = QRect()
        self._rubber_band.hide()
        self.showFullScreen()
        self.activateWindow()
        logger.debug("ScreenshotOverlay shown full-screen")

    # ------------------------------------------------------------------
    # Qt event overrides
    # ------------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._selection = QRect(self._origin, self._origin)
            self._rubber_band.setGeometry(QRect(self._origin, self._origin).normalized())
            self._rubber_band.show()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if not self._origin.isNull():
            current: QPoint = event.position().toPoint()
            self._selection = QRect(self._origin, current).normalized()
            self._rubber_band.setGeometry(self._selection)
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and not self._origin.isNull():
            self._rubber_band.hide()
            rect: QRect = QRect(self._origin, event.position().toPoint()).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.hide()
                self._grab_region(rect)
            else:
                logger.warning("Selection too small (%dx%d), ignoring", rect.width(), rect.height())
                self._origin = QPoint()
                self._selection = QRect()
            self._origin = QPoint()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key.Key_Escape:
            logger.debug("Capture cancelled via ESC")
            self.hide()
            self.capture_cancelled.emit()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Semi-transparent dark overlay covering the whole screen
        overlay_color = QColor(0, 0, 0, 128)
        painter.fillRect(self.rect(), overlay_color)

        # Cut out the selected region so it appears bright/clear
        if not self._selection.isNull() and self._selection.isValid():
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._selection, Qt.GlobalColor.transparent)

        painter.end()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _grab_region(self, rect: QRect) -> None:
        """Grab the screen region and emit capture_complete with PNG bytes."""
        screen = QApplication.primaryScreen()
        if screen is None:
            logger.error("No primary screen found; aborting capture")
            self.capture_cancelled.emit()
            return

        dpr: float = screen.devicePixelRatio()
        # Qt6 grabWindow expects logical coordinates; it handles DPR internally.
        # Do NOT manually multiply by DPR — that causes coordinate offset on high-DPI screens.
        x: int = int(rect.x())
        y: int = int(rect.y())
        w: int = int(rect.width())
        h: int = int(rect.height())

        logger.debug("Grabbing region x=%d y=%d w=%d h=%d (DPR=%.2f)", x, y, w, h, dpr)

        pixmap: QPixmap = screen.grabWindow(0, x, y, w, h)
        if pixmap.isNull():
            logger.error("grabWindow returned a null pixmap")
            self.capture_cancelled.emit()
            return

        buffer = QBuffer()
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        png_bytes: bytes = bytes(buffer.data())
        buffer.close()

        logger.debug("Capture complete, size=%d bytes", len(png_bytes))
        self.capture_complete.emit(png_bytes)
