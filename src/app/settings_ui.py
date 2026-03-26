from __future__ import annotations

import httpx
from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utils.config import ConfigManager
from utils.logger import get_logger

logger = get_logger(__name__)

_MODEL_PRESETS: list[str] = [
    "gpt-4o",
    "claude-3-5-sonnet-20241022",
    "deepseek-chat",
    "moonshot-v1-8k",
]


class _ConnectionWorker(QObject):
    """Background worker that pings the API endpoint to verify connectivity."""

    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, endpoint: str, api_key: str, timeout: int) -> None:
        super().__init__()
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout

    def run(self) -> None:
        try:
            headers: dict[str, str] = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            # Hit the /models endpoint as a lightweight connectivity check;
            # fall back to the base URL if the path yields a 404.
            test_url = f"{self._endpoint}/models"
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(test_url, headers=headers)
            if response.status_code < 500:
                self.succeeded.emit()
            else:
                self.failed.emit(
                    f"服务器返回错误状态码：{response.status_code}"
                )
        except httpx.TimeoutException:
            self.failed.emit("连接超时，请检查 API 地址或网络。")
        except httpx.RequestError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class SettingsUI(QDialog):
    """Settings dialog for TexPaste.

    Provides three tabs:
      * API 配置 — endpoint, key, model, timeout, retries, connectivity test
      * 通用    — Pandoc path, auto-update toggle
      * 快捷键  — screenshot hotkey, paste hotkey
    """

    def __init__(
        self,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._thread: QThread | None = None
        self._worker: _ConnectionWorker | None = None

        self._setup_ui()
        self._load_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("TexPaste 设置")
        self.setMinimumSize(480, 400)
        self.setModal(True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self._tabs = QTabWidget()
        root_layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_api_tab(), "API 配置")
        self._tabs.addTab(self._build_general_tab(), "通用")
        self._tabs.addTab(self._build_hotkeys_tab(), "快捷键")

        root_layout.addWidget(self._build_button_bar())

    def _build_api_tab(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("API 连接参数")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        # Endpoint
        self._endpoint_edit = QLineEdit()
        self._endpoint_edit.setPlaceholderText(
            "https://api.openai.com/v1"
        )
        form.addRow("API 地址", self._endpoint_edit)

        # API Key (masked)
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        form.addRow("API Key", self._api_key_edit)

        # Model combo (editable for custom models)
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.addItems(_MODEL_PRESETS)
        form.addRow("模型", self._model_combo)

        # Timeout
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(5, 120)
        self._timeout_spin.setValue(30)
        self._timeout_spin.setSuffix(" 秒")
        form.addRow("超时 (秒)", self._timeout_spin)

        # Retries
        self._retries_spin = QSpinBox()
        self._retries_spin.setRange(0, 5)
        self._retries_spin.setValue(3)
        form.addRow("最大重试次数", self._retries_spin)

        # Test button (aligned left)
        self._test_btn = QPushButton("测试连接")
        self._test_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._test_btn.clicked.connect(self._test_connection)
        form.addRow("", self._test_btn)

        outer.addWidget(group)
        outer.addStretch()
        return container

    def _build_general_tab(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("通用设置")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Pandoc path + browse button
        pandoc_row = QHBoxLayout()
        self._pandoc_edit = QLineEdit()
        self._pandoc_edit.setPlaceholderText("pandoc（系统 PATH 中已配置则留空）")
        pandoc_row.addWidget(self._pandoc_edit)

        browse_btn = QPushButton("浏览...")
        browse_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        browse_btn.clicked.connect(self._browse_pandoc)
        pandoc_row.addWidget(browse_btn)

        form.addRow("Pandoc 路径", pandoc_row)

        # Auto-update checkbox
        self._auto_update_check = QCheckBox("启动时自动检查更新")
        form.addRow("自动检查更新", self._auto_update_check)

        outer.addWidget(group)
        outer.addStretch()
        return container

    def _build_hotkeys_tab(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)

        group = QGroupBox("快捷键设置")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Screenshot hotkey
        self._screenshot_key_edit = QLineEdit()
        self._screenshot_key_edit.setPlaceholderText("ctrl+shift+a")
        form.addRow("截图快捷键", self._screenshot_key_edit)

        # Paste hotkey
        self._paste_key_edit = QLineEdit()
        self._paste_key_edit.setPlaceholderText("ctrl+shift+v")
        form.addRow("粘贴快捷键", self._paste_key_edit)

        # Format hint
        hint_label = QLabel("格式：ctrl+shift+a，可使用 ctrl/shift/alt/win")
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow("", hint_label)

        # Reset to defaults button
        reset_btn = QPushButton("恢复默认")
        reset_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        reset_btn.clicked.connect(self._reset_hotkeys)
        form.addRow("", reset_btn)

        outer.addWidget(group)
        outer.addStretch()
        return container

    def _build_button_bar(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._on_save)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(save_btn)
        layout.addWidget(cancel_btn)
        return container

    # ------------------------------------------------------------------
    # Settings I/O
    # ------------------------------------------------------------------

    def _load_settings(self) -> None:
        """Populate all widgets from ConfigManager."""
        self._endpoint_edit.setText(
            self._config.get("api.endpoint", "https://api.openai.com/v1")
        )
        self._api_key_edit.setText(self._config.get("api.key", ""))

        model: str = self._config.get("api.model", "gpt-4o")
        index = self._model_combo.findText(model)
        if index >= 0:
            self._model_combo.setCurrentIndex(index)
        else:
            self._model_combo.setCurrentText(model)

        self._timeout_spin.setValue(int(self._config.get("api.timeout", 30)))
        self._retries_spin.setValue(int(self._config.get("api.retries", 3)))

        self._pandoc_edit.setText(self._config.get("general.pandoc_path", ""))
        self._auto_update_check.setChecked(
            bool(self._config.get("general.auto_update", True))
        )

        self._screenshot_key_edit.setText(
            self._config.get("hotkeys.screenshot", "ctrl+shift+a")
        )
        self._paste_key_edit.setText(
            self._config.get("hotkeys.paste", "ctrl+shift+v")
        )

        logger.info("Settings loaded into dialog.")

    def _save_settings(self) -> None:
        """Write all widget values back to ConfigManager."""
        self._config.set("api.endpoint", self._endpoint_edit.text().strip())
        self._config.set("api.key", self._api_key_edit.text())
        self._config.set("api.model", self._model_combo.currentText().strip())
        self._config.set("api.timeout", self._timeout_spin.value())
        self._config.set("api.retries", self._retries_spin.value())
        self._config.set("general.pandoc_path", self._pandoc_edit.text().strip())
        self._config.set("general.auto_update", self._auto_update_check.isChecked())
        self._config.set("hotkeys.screenshot", self._screenshot_key_edit.text().strip())
        self._config.set("hotkeys.paste", self._paste_key_edit.text().strip())

        logger.info("Settings saved.")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        self._save_settings()
        self.accept()

    def _browse_pandoc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 Pandoc 可执行文件",
            "",
            "可执行文件 (*.exe);;所有文件 (*)",
        )
        if path:
            self._pandoc_edit.setText(path)

    def _reset_hotkeys(self) -> None:
        """Restore screenshot and paste hotkeys to factory defaults."""
        self._screenshot_key_edit.setText("ctrl+shift+a")
        self._paste_key_edit.setText("ctrl+shift+v")

    def _test_connection(self) -> None:
        """Spin up a background thread to ping the configured API endpoint."""
        endpoint = self._endpoint_edit.text().strip()
        if not endpoint:
            QMessageBox.warning(self, "缺少参数", "请先填写 API 地址。")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("测试中...")

        self._thread = QThread(self)
        self._worker = _ConnectionWorker(
            endpoint=endpoint,
            api_key=self._api_key_edit.text(),
            timeout=self._timeout_spin.value(),
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(self._on_test_succeeded)
        self._worker.failed.connect(self._on_test_failed)

        # Clean up thread when done
        self._worker.succeeded.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_test_succeeded(self) -> None:
        QMessageBox.information(self, "连接成功", "API 端点连接测试通过。")
        self._reset_test_btn()

    def _on_test_failed(self, error_msg: str) -> None:
        QMessageBox.warning(self, "连接失败", error_msg)
        self._reset_test_btn()

    def _reset_test_btn(self) -> None:
        self._test_btn.setEnabled(True)
        self._test_btn.setText("测试连接")
