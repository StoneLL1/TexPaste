from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSlot as Slot
from PyQt6.QtWidgets import QSystemTrayIcon

from app.screenshot_overlay import ScreenshotOverlay
from app.tray import TrayManager
from core.clipboard import ClipboardManager, detect_content_type
from core.hotkey import HotkeyManager
from core.recognizer import RecognizerService
from core.screenshot import ScreenshotCapture
from core.word_paste import WordPasteService, WordPasteWorker, is_word_wps_active
from models.enums import AppState, ContentType
from utils.config import ConfigManager
from utils.db import HistoryRepository
from utils.logger import get_app_data_dir, get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("controller")

CLEANUP_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 hours


class AppController(QObject):
    """
    Main application controller.
    Holds all core services, manages the application state machine,
    and wires Qt signals between components.
    """

    def __init__(self, config: ConfigManager) -> None:
        super().__init__()
        self.config = config
        self._state = AppState.IDLE
        self._paused = False
        self._last_screenshot_bytes: bytes | None = None  # For diagnostics

        self._init_services()
        self._connect_signals()
        self._start_services()
        self._schedule_cleanup()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_services(self) -> None:
        app_data_dir = get_app_data_dir()

        self.tray = TrayManager(parent=self)
        self.hotkey_manager = HotkeyManager(parent=self)
        self.screenshot_capture = ScreenshotCapture(parent=self)
        self.clipboard = ClipboardManager()
        self.recognizer = RecognizerService(self.config, parent=self)
        self.word_paste_service = WordPasteService(
            pandoc_path=self.config.get("pandoc.executable", "pandoc")
        )
        self.history_repo = HistoryRepository(app_data_dir / "history.db")
        self._paste_worker: WordPasteWorker | None = None
        self._paste_thread = None

    def _connect_signals(self) -> None:
        # Hotkeys
        self.hotkey_manager.screenshot_triggered.connect(self._on_screenshot_hotkey)
        self.hotkey_manager.paste_triggered.connect(self._on_paste_hotkey)

        # Screenshot
        self.screenshot_capture.capture_complete.connect(self._on_capture_complete)
        self.screenshot_capture.capture_cancelled.connect(self._on_capture_cancelled)

        # Recognizer
        self.recognizer.recognition_complete.connect(self._on_recognition_complete)
        self.recognizer.recognition_failed.connect(self._on_recognition_failed)
        self.recognizer.recognition_progress.connect(self._on_recognition_progress)

        # Tray
        self.tray.settings_requested.connect(self._on_settings_requested)
        self.tray.history_requested.connect(self._on_history_requested)
        self.tray.pause_toggled.connect(self._on_pause_toggled)
        self.tray.exit_requested.connect(self._on_exit_requested)
        self.tray.update_check_requested.connect(self._on_update_check_requested)

    def _start_services(self) -> None:
        # Update template label in tray
        current_template = self.config.get("templates.current", "智能识别")
        self.tray.update_template_label(current_template)

        screenshot_key = self.config.get("hotkeys.screenshot", "ctrl+shift+a")
        paste_key = self.config.get("hotkeys.paste", "ctrl+shift+v")
        if not self.hotkey_manager.register(screenshot_key, paste_key):
            logger.error("Failed to register hotkeys")
            if self._should_notify("error"):
                self.tray.show_notification(
                    "TexPaste",
                    "全局快捷键注册失败，请检查是否有冲突。",
                    QSystemTrayIcon.MessageIcon.Warning,
                )

    def _schedule_cleanup(self) -> None:
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(CLEANUP_INTERVAL_MS)
        self._cleanup_timer.timeout.connect(self._run_cleanup)
        self._cleanup_timer.start()
        # Also run once at startup
        QTimer.singleShot(5000, self._run_cleanup)

    # ------------------------------------------------------------------
    # State machine helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: AppState) -> None:
        logger.debug("State transition: %s → %s", self._state, state)
        self._state = state

    def _should_notify(self, category: str) -> bool:
        """Check if notifications are enabled for *category*."""
        return bool(self.config.get(f"notifications.{category}", True))

    # ------------------------------------------------------------------
    # Hotkey handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_screenshot_hotkey(self) -> None:
        if self._paused or self._state != AppState.IDLE:
            logger.debug("Screenshot hotkey ignored (paused=%s, state=%s)", self._paused, self._state)
            return
        logger.info("Screenshot hotkey triggered")
        self._set_state(AppState.CAPTURING)
        self.tray.set_status_loading()
        self.screenshot_capture.start_capture()

    @Slot()
    def _on_paste_hotkey(self) -> None:
        if self._paused or self._state != AppState.IDLE:
            logger.debug("Paste hotkey ignored (paused=%s, state=%s)", self._paused, self._state)
            return

        is_active, app_name = is_word_wps_active()
        if not is_active:
            if self._should_notify("error"):
                self.tray.show_notification(
                    "TexPaste",
                    "请先打开 Word 或 WPS 并将光标置于要插入的位置。",
                    QSystemTrayIcon.MessageIcon.Information,
                )
            return

        content = self.clipboard.get_text()
        if not content.strip():
            if self._should_notify("error"):
                self.tray.show_notification(
                    "TexPaste",
                    "剪贴板为空，请先识别内容。",
                    QSystemTrayIcon.MessageIcon.Warning,
                )
            return

        self._set_state(AppState.PASTING)
        self.tray.set_status_loading()
        logger.info("Smart paste triggered for %s", app_name)

        content_type = detect_content_type(content)
        self._start_paste_worker(content, content_type)

    # ------------------------------------------------------------------
    # Screenshot handlers
    # ------------------------------------------------------------------

    @Slot(bytes)
    def _on_capture_complete(self, image_bytes: bytes) -> None:
        logger.info("Screenshot captured (%d bytes)", len(image_bytes))
        self._last_screenshot_bytes = image_bytes  # Save for diagnostics
        self._set_state(AppState.RECOGNIZING)
        self.recognizer.recognize(image_bytes)

    @Slot()
    def _on_capture_cancelled(self) -> None:
        logger.info("Screenshot cancelled")
        self._set_state(AppState.IDLE)
        self.tray.set_status_normal()

    # ------------------------------------------------------------------
    # Recognition handlers
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _on_recognition_complete(self, result: str, content_type_value: str) -> None:
        logger.info("Recognition complete: type=%s, length=%d", content_type_value, len(result))

        # LLM returned [UNREADABLE] — treat as recognition failure
        if result.strip() == "[UNREADABLE]":
            logger.warning("LLM returned [UNREADABLE] — image could not be recognised by the model")
            self._on_recognition_failed("图片无法识别，请检查：① 截图区域是否包含清晰内容；② API 模型是否支持图像输入（视觉模型）")
            return

        self.clipboard.set_text(result)

        # Save to history (thumbnail not stored in this path)
        model = self.config.get("api.model", "")
        self.history_repo.save(
            content_type=content_type_value,
            result=result,
            api_model=model,
        )

        self._set_state(AppState.IDLE)
        self.tray.set_status_normal()
        if self._should_notify("recognition_success"):
            self.tray.show_notification(
                "TexPaste",
                "识别完成，已复制到剪贴板。",
                QSystemTrayIcon.MessageIcon.Information,
            )

    @Slot(str)
    def _on_recognition_failed(self, error_msg: str) -> None:
        logger.error("Recognition failed: %s", error_msg)

        # Save failed screenshot for diagnostics
        if self._last_screenshot_bytes:
            try:
                app_data_dir = get_app_data_dir()
                logs_dir = app_data_dir / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_path = logs_dir / f"debug_screenshot_{timestamp}.png"
                debug_path.write_bytes(self._last_screenshot_bytes)
                logger.info("[DIAG] Failed screenshot saved to: %s", debug_path)
            except Exception as e:
                logger.warning("[DIAG] Could not save debug screenshot: %s", e)

        self._set_state(AppState.IDLE)
        self.tray.set_status_error()
        if self._should_notify("error"):
            self.tray.show_notification(
                "TexPaste",
                f"识别失败：{error_msg}",
                QSystemTrayIcon.MessageIcon.Critical,
            )
        # Reset icon to normal after 5 seconds
        QTimer.singleShot(5000, self.tray.set_status_normal)

    @Slot(str)
    def _on_recognition_progress(self, status: str) -> None:
        logger.debug("Recognition progress: %s", status)

    # ------------------------------------------------------------------
    # Paste worker
    # ------------------------------------------------------------------

    def _start_paste_worker(self, content: str, content_type: ContentType) -> None:
        from PyQt6.QtCore import QThread

        thread = QThread(self)
        pandoc_path = self.config.get("pandoc.executable", "pandoc")
        worker = WordPasteWorker(content, content_type, pandoc_path=pandoc_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.paste_complete.connect(self._on_paste_complete)
        worker.paste_complete.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)

        self._paste_worker = worker
        self._paste_thread = thread
        thread.start()

    @Slot(bool, str)
    def _on_paste_complete(self, success: bool, message: str) -> None:
        self._set_state(AppState.IDLE)
        if success:
            self.tray.set_status_normal()
            if self._should_notify("paste_success"):
                self.tray.show_notification("TexPaste", message,
                                            QSystemTrayIcon.MessageIcon.Information)
        else:
            self.tray.set_status_error()
            if self._should_notify("error"):
                self.tray.show_notification("TexPaste", f"粘贴失败：{message}",
                                            QSystemTrayIcon.MessageIcon.Warning)
            QTimer.singleShot(5000, self.tray.set_status_normal)

    # ------------------------------------------------------------------
    # Tray handlers
    # ------------------------------------------------------------------

    @Slot()
    def _on_settings_requested(self) -> None:
        from app.settings_ui import SettingsUI

        dialog = SettingsUI(self.config)
        if dialog.exec():
            # Settings saved — reload hotkeys in case they changed
            screenshot_key = self.config.get("hotkeys.screenshot", "ctrl+shift+a")
            paste_key = self.config.get("hotkeys.paste", "ctrl+shift+v")
            self.hotkey_manager.update_hotkeys(screenshot_key, paste_key)

            # Update template label in tray
            current_template = self.config.get("templates.current", "智能识别")
            self.tray.update_template_label(current_template)

            logger.info("Settings updated and hotkeys refreshed")

    @Slot()
    def _on_history_requested(self) -> None:
        from app.history_ui import HistoryUI

        dialog = HistoryUI(self.history_repo, self.clipboard)
        dialog.exec()

    @Slot(bool)
    def _on_pause_toggled(self, paused: bool) -> None:
        self._paused = paused
        logger.info("Application %s", "paused" if paused else "resumed")

    @Slot()
    def _on_exit_requested(self) -> None:
        logger.info("Exit requested")
        self.hotkey_manager.unregister()
        self.history_repo.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    @Slot()
    def _on_update_check_requested(self) -> None:
        from utils.updater import UpdateChecker
        checker = UpdateChecker(self.config)
        checker.check_once()

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    @Slot()
    def _run_cleanup(self) -> None:
        retention_days = self.config.get("history.retention_days", 7)
        deleted = self.history_repo.delete_expired(retention_days=retention_days)
        if deleted:
            logger.info("Cleanup: deleted %d expired history records", deleted)
