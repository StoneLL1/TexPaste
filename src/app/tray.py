from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from utils.logger import get_logger

logger = get_logger(__name__)


class TrayManager(QObject):
    settings_requested = Signal()
    history_requested = Signal()
    pause_toggled = Signal(bool)
    exit_requested = Signal()
    update_check_requested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._is_paused: bool = False

        self._tray = QSystemTrayIcon(self._load_icon("tray_normal.png"), self)
        self._tray.setToolTip("TexPaste")

        menu = QMenu()

        self._template_action = QAction("当前模板: 智能识别", self)
        self._template_action.setEnabled(False)
        menu.addAction(self._template_action)

        menu.addSeparator()

        history_action = QAction("历史记录", self)
        history_action.triggered.connect(self.history_requested)
        menu.addAction(history_action)

        menu.addSeparator()

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.settings_requested)
        menu.addAction(settings_action)

        self._pause_action = QAction("暂停", self)
        self._pause_action.triggered.connect(self._on_pause_toggled)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        update_action = QAction("检查更新", self)
        update_action.triggered.connect(self.update_check_requested)
        menu.addAction(update_action)

        menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.exit_requested)
        menu.addAction(exit_action)

        self._tray.setContextMenu(menu)
        self._tray.show()

        logger.info("TrayManager initialized")

    def set_status_normal(self) -> None:
        self._tray.setIcon(self._load_icon("tray_normal.png"))
        self._tray.setToolTip("TexPaste - 就绪")

    def set_status_loading(self) -> None:
        self._tray.setIcon(self._load_icon("tray_loading.png"))
        self._tray.setToolTip("TexPaste - 识别中...")

    def set_status_error(self) -> None:
        self._tray.setIcon(self._load_icon("tray_error.png"))
        self._tray.setToolTip("TexPaste - 错误")

    def set_status_paused(self) -> None:
        self._tray.setIcon(self._load_icon("tray_paused.png"))
        self._tray.setToolTip("TexPaste - 已暂停")

    def show_notification(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
    ) -> None:
        self._tray.showMessage(title, message, icon, 3000)

    @Slot()
    def _on_pause_toggled(self) -> None:
        self._is_paused = not self._is_paused
        if self._is_paused:
            self._pause_action.setText("恢复")
            self.set_status_paused()
            logger.info("TexPaste paused")
        else:
            self._pause_action.setText("暂停")
            self.set_status_normal()
            logger.info("TexPaste resumed")
        self.pause_toggled.emit(self._is_paused)

    def update_template_label(self, name: str) -> None:
        """Update the template label in the tray menu."""
        self._template_action.setText(f"当前模板: {name}")

    @staticmethod
    def _load_icon(name: str) -> QIcon:
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / name
        if icon_path.exists():
            return QIcon(str(icon_path))
        logger.warning("Icon not found: %s", icon_path)
        return QIcon()
