from __future__ import annotations

import webbrowser
from pathlib import Path

import httpx
from PyQt6.QtCore import QObject, Qt, QThread
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.hotkey_recorder import HotkeyRecorder
from utils.config import ConfigManager
from utils.logger import get_logger
from utils.updater import UpdateChecker

logger = get_logger(__name__)


def _get_connection_error_message(status_code: int, model: str, endpoint: str) -> str:
    """Convert HTTP status code and context to user-friendly error message.

    Args:
        status_code: HTTP response status code
        model: Model name being tested (empty string if not testing a model)
        endpoint: API endpoint URL

    Returns:
        User-friendly error message with diagnostic hints
    """
    if status_code == 401:
        return "❌ API Key 无效或缺失，请检查 API Key。"
    elif status_code == 404:
        if model:
            return f"❌ 模型 '{model}' 不存在或 API 端点不正确。请检查：\n① 模型名称是否正确\n② API URL 是否完整"
        else:
            return "❌ API 端点不存在。请检查：\n① API URL 地址是否正确\n② URL 是否以 /v1 结尾"
    elif status_code == 400:
        if model:
            return f"❌ 模型 '{model}' 可能不支持或请求格式错误。请检查：\n① 模型名称拼写\n② API 是否支持此模型"
        else:
            return "❌ 请求格式错误。请检查 API 配置。"
    elif status_code == 403:
        return "❌ 无权限访问此 API。请检查 API Key 是否有必要的权限。"
    elif status_code >= 500:
        return f"❌ API 服务器出现问题 (HTTP {status_code})。请稍后重试或联系 API 提供商。"
    else:
        return f"❌ 连接失败 (HTTP {status_code})。请检查 API 配置。"


_PROMPTS_DIR = Path(__file__).parent.parent / "resources" / "prompts"

_PRESET_TEMPLATE_NAMES: list[str] = ["智能识别", "纯LaTeX", "纯Markdown", "纯文本"]

_PRESET_TEMPLATE_FILES: dict[str, str] = {
    "智能识别": "recognize.txt",
    "纯LaTeX": "pure_latex.txt",
    "纯Markdown": "pure_markdown.txt",
    "纯文本": "pure_text.txt",
}

_MAX_CUSTOM_TEMPLATES = 10

# 资源路径
_ICONS_DIR = Path(__file__).parent.parent / "resources" / "icons"
_CHECKMARK_ICON_PATH = str(_ICONS_DIR / "checkmark.png")

# 黑白灰配色常量
_COLOR_PRIMARY_BG = "#FFFFFF"
_COLOR_SECONDARY_BG = "#F5F5F5"
_COLOR_TERTIARY_BG = "#EEEEEE"
_COLOR_TEXT_PRIMARY = "#333333"
_COLOR_TEXT_SECONDARY = "#666666"
_COLOR_BORDER = "#E0E0E0"
_COLOR_BUTTON_BG = "#F0F0F0"
_COLOR_BUTTON_HOVER = "#E0E0E0"
_COLOR_SELECTED = "#DDDDDD"

# 样式表
_MAIN_STYLESHEET = f"""
QDialog {{
    background-color: {_COLOR_PRIMARY_BG};
    color: {_COLOR_TEXT_PRIMARY};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}}

QTabWidget::pane {{
    border: 1px solid {_COLOR_BORDER};
    background-color: {_COLOR_PRIMARY_BG};
}}

QTabBar::tab {{
    background-color: {_COLOR_SECONDARY_BG};
    color: {_COLOR_TEXT_SECONDARY};
    padding: 8px 16px;
    border: 1px solid {_COLOR_BORDER};
    border-bottom: none;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {_COLOR_PRIMARY_BG};
    color: {_COLOR_TEXT_PRIMARY};
    font-weight: bold;
}}

QTabBar::tab:hover {{
    background-color: {_COLOR_TERTIARY_BG};
}}

QGroupBox {{
    border: 1px solid {_COLOR_BORDER};
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {_COLOR_TEXT_PRIMARY};
}}

QFormLayout {{
    spacing: 10px;
}}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {_COLOR_PRIMARY_BG};
    border: 1px solid {_COLOR_BORDER};
    border-radius: 4px;
    padding: 6px 8px;
    color: {_COLOR_TEXT_PRIMARY};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {_COLOR_TEXT_SECONDARY};
}}

QLineEdit:disabled, QComboBox:disabled {{
    background-color: {_COLOR_SECONDARY_BG};
    color: {_COLOR_TEXT_SECONDARY};
}}

QPushButton {{
    background-color: {_COLOR_BUTTON_BG};
    border: 1px solid {_COLOR_BORDER};
    border-radius: 4px;
    padding: 6px 16px;
    color: {_COLOR_TEXT_PRIMARY};
    min-width: 70px;
}}

QPushButton:hover {{
    background-color: {_COLOR_BUTTON_HOVER};
}}

QPushButton:pressed {{
    background-color: {_COLOR_SELECTED};
}}

QPushButton:disabled {{
    background-color: {_COLOR_SECONDARY_BG};
    color: {_COLOR_TEXT_SECONDARY};
}}

QPushButton[default="true"] {{
    background-color: {_COLOR_TEXT_PRIMARY};
    color: {_COLOR_PRIMARY_BG};
    border: 1px solid {_COLOR_TEXT_PRIMARY};
}}

QPushButton[default="true"]:hover {{
    background-color: {_COLOR_TEXT_SECONDARY};
}}

QCheckBox {{
    spacing: 8px;
    color: {_COLOR_TEXT_PRIMARY};
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {_COLOR_BORDER};
    border-radius: 3px;
    background-color: {_COLOR_PRIMARY_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {_COLOR_PRIMARY_BG};
    border: 1px solid {_COLOR_TEXT_PRIMARY};
    image: url({_CHECKMARK_ICON_PATH.replace(chr(92), "/")});
}}

QListWidget {{
    background-color: {_COLOR_PRIMARY_BG};
    border: 1px solid {_COLOR_BORDER};
    border-radius: 4px;
    outline: none;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-bottom: 1px solid {_COLOR_SECONDARY_BG};
}}

QListWidget::item:selected {{
    background-color: {_COLOR_SELECTED};
    color: {_COLOR_TEXT_PRIMARY};
}}

QListWidget::item:hover {{
    background-color: {_COLOR_TERTIARY_BG};
}}

QPlainTextEdit {{
    background-color: {_COLOR_PRIMARY_BG};
    border: 1px solid {_COLOR_BORDER};
    border-radius: 4px;
    padding: 8px;
    color: {_COLOR_TEXT_PRIMARY};
}}

QPlainTextEdit:focus {{
    border: 1px solid {_COLOR_TEXT_SECONDARY};
}}

QLabel {{
    color: {_COLOR_TEXT_PRIMARY};
}}

QScrollBar:vertical {{
    width: 10px;
    background: {_COLOR_SECONDARY_BG};
}}

QScrollBar::handle:vertical {{
    background: {_COLOR_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {_COLOR_TEXT_SECONDARY};
}}

QMessageBox {{
    background-color: {_COLOR_PRIMARY_BG};
}}
"""

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

    def __init__(self, endpoint: str, api_key: str, timeout: int, model: str = "") -> None:
        super().__init__()
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._model = model
        self._logger = get_logger("settings.connection_worker")

    def run(self) -> None:
        try:
            headers: dict[str, str] = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            # If model is specified, test it directly by sending a minimal request.
            # Otherwise, test the /models endpoint as a lightweight connectivity check.
            if self._model:
                test_url = f"{self._endpoint}/chat/completions"
                self._logger.debug(
                    "Testing API connection with model: %s at %s", self._model, test_url
                )
                payload = {
                    "model": self._model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                }
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.post(test_url, json=payload, headers=headers)
            else:
                test_url = f"{self._endpoint}/models"
                self._logger.debug("Testing API connection: %s", test_url)
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.get(test_url, headers=headers)

            self._logger.debug("API response status: %d", response.status_code)
            if response.is_success:
                self.succeeded.emit()
            else:
                error_msg = _get_connection_error_message(
                    response.status_code, self._model, self._endpoint
                )
                self.failed.emit(error_msg)
        except httpx.TimeoutException:
            self._logger.error("API connection timeout")
            self.failed.emit("连接超时，请检查 API 地址或网络。")
        except httpx.RequestError as exc:
            self._logger.error("API connection error: %s", exc)
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Unexpected error during API test: %s", exc)
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
        self.setMinimumSize(640, 480)
        self.setModal(True)
        self.setWindowIcon(self._load_icon())
        self.setStyleSheet(_MAIN_STYLESHEET)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self._tabs = QTabWidget()
        root_layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_api_tab(), "API 配置")
        self._tabs.addTab(self._build_general_tab(), "通用")
        self._tabs.addTab(self._build_hotkeys_tab(), "快捷键")
        self._tabs.addTab(self._build_templates_tab(), "模板")
        self._tabs.addTab(self._build_about_tab(), "关于")

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
        self._endpoint_edit.setPlaceholderText("https://api.openai.com/v1")
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

        # Model hint - inform user about multimodal requirement
        model_hint = QLabel("💡 请配置支持图像输入的多模态大模型（如 GPT-4o、Claude Vision）")
        model_hint.setStyleSheet(f"color: {_COLOR_TEXT_SECONDARY}; font-size: 11px; padding-left: 4px;")
        model_hint.setWordWrap(True)
        form.addRow("", model_hint)

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
        self._test_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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
        browse_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        browse_btn.clicked.connect(self._browse_pandoc)
        pandoc_row.addWidget(browse_btn)

        form.addRow("Pandoc 路径", pandoc_row)

        # Auto-update checkbox
        self._auto_update_check = QCheckBox("启动时自动检查更新")
        form.addRow("自动检查更新", self._auto_update_check)

        outer.addWidget(group)

        # Notification settings
        notif_group = QGroupBox("通知设置")
        notif_layout = QVBoxLayout(notif_group)

        self._notif_recognition = QCheckBox("识别成功时显示通知")
        self._notif_paste = QCheckBox("粘贴成功时显示通知")
        self._notif_error = QCheckBox("出现错误时显示通知")

        notif_layout.addWidget(self._notif_recognition)
        notif_layout.addWidget(self._notif_paste)
        notif_layout.addWidget(self._notif_error)

        outer.addWidget(notif_group)
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
        self._screenshot_key_recorder = HotkeyRecorder()
        form.addRow("截图快捷键", self._screenshot_key_recorder)

        # Paste hotkey
        self._paste_key_recorder = HotkeyRecorder()
        form.addRow("粘贴快捷键", self._paste_key_recorder)

        # Recording hint
        hint_label = QLabel("点击输入框后按下快捷键组合即可自动录制")
        hint_label.setStyleSheet(f"color: {_COLOR_TEXT_SECONDARY}; font-size: 11px;")
        form.addRow("", hint_label)

        # Reset to defaults button
        reset_btn = QPushButton("恢复默认")
        reset_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        reset_btn.clicked.connect(self._reset_hotkeys)
        form.addRow("", reset_btn)

        outer.addWidget(group)
        outer.addStretch()
        return container

    def _build_templates_tab(self) -> QWidget:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)

        # Splitter: list on left, editor on right
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: template list
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._template_list = QListWidget()
        self._template_list.currentRowChanged.connect(self._on_template_selection_changed)
        left_layout.addWidget(self._template_list)

        # Buttons below the list
        btn_row = QHBoxLayout()
        self._add_template_btn = QPushButton("添加")
        self._add_template_btn.clicked.connect(self._add_custom_template)
        self._rename_template_btn = QPushButton("重命名")
        self._rename_template_btn.clicked.connect(self._rename_custom_template)
        self._delete_template_btn = QPushButton("删除")
        self._delete_template_btn.clicked.connect(self._delete_custom_template)
        btn_row.addWidget(self._add_template_btn)
        btn_row.addWidget(self._rename_template_btn)
        btn_row.addWidget(self._delete_template_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_widget)

        # Right side: prompt editor
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._template_editor = QPlainTextEdit()
        self._template_editor.setPlaceholderText("选择模板以查看/编辑提示词内容...")
        right_layout.addWidget(self._template_editor)

        # "Set as current" row
        current_row = QHBoxLayout()
        self._set_current_btn = QPushButton("设为当前")
        self._set_current_btn.clicked.connect(self._set_template_as_current)
        self._current_template_label = QLabel("当前: 智能识别")
        current_row.addWidget(self._set_current_btn)
        current_row.addWidget(self._current_template_label)
        current_row.addStretch()
        right_layout.addLayout(current_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([200, 400])

        outer.addWidget(splitter)
        return container

    # ------------------------------------------------------------------
    # Template management slots
    # ------------------------------------------------------------------

    def _populate_template_list(self) -> None:
        """Refresh the template list widget from internal state."""
        self._template_list.blockSignals(True)
        current_row = self._template_list.currentRow()
        self._template_list.clear()

        for name in _PRESET_TEMPLATE_NAMES:
            item = QListWidgetItem(f"\U0001f512 {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._template_list.addItem(item)

        for t in self._custom_templates:
            item = QListWidgetItem(t["name"])
            item.setData(Qt.ItemDataRole.UserRole, t["name"])
            self._template_list.addItem(item)

        # Restore selection
        if 0 <= current_row < self._template_list.count():
            self._template_list.setCurrentRow(current_row)
        elif self._template_list.count() > 0:
            self._template_list.setCurrentRow(0)

        self._template_list.blockSignals(False)
        self._update_template_buttons()

    def _on_template_selection_changed(self, row: int) -> None:
        """Handle template list selection change."""
        # Save current editor content to previously selected custom template
        self._save_editor_to_current_custom()

        if row < 0 or row >= self._template_list.count():
            return

        item = self._template_list.item(row)
        name = item.data(Qt.ItemDataRole.UserRole)

        if name in _PRESET_TEMPLATE_NAMES:
            # Preset: load from file, read-only
            file_name = _PRESET_TEMPLATE_FILES[name]
            path = _PROMPTS_DIR / file_name
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                content = f"(无法读取预设模板文件: {file_name})"
            self._template_editor.setPlainText(content)
            self._template_editor.setReadOnly(True)
        else:
            # Custom: load from memory, editable
            for t in self._custom_templates:
                if t["name"] == name:
                    self._template_editor.setPlainText(t["prompt"])
                    break
            self._template_editor.setReadOnly(False)

        self._update_template_buttons()
        self._prev_selected_name = name

    def _save_editor_to_current_custom(self) -> None:
        """Save current editor content back to the in-memory custom template."""
        if not hasattr(self, "_prev_selected_name"):
            return
        prev = self._prev_selected_name
        if prev in _PRESET_TEMPLATE_NAMES:
            return
        content = self._template_editor.toPlainText()
        for t in self._custom_templates:
            if t["name"] == prev:
                t["prompt"] = content
                break

    def _update_template_buttons(self) -> None:
        """Enable/disable buttons based on current selection."""
        row = self._template_list.currentRow()
        is_preset = row < len(_PRESET_TEMPLATE_NAMES)
        has_selection = row >= 0

        self._rename_template_btn.setEnabled(has_selection and not is_preset)
        self._delete_template_btn.setEnabled(has_selection and not is_preset)
        self._set_current_btn.setEnabled(has_selection)
        self._add_template_btn.setEnabled(len(self._custom_templates) < _MAX_CUSTOM_TEMPLATES)

    def _get_all_template_names(self) -> list[str]:
        """Return all template names (preset + custom)."""
        return list(_PRESET_TEMPLATE_NAMES) + [t["name"] for t in self._custom_templates]

    def _add_custom_template(self) -> None:
        if len(self._custom_templates) >= _MAX_CUSTOM_TEMPLATES:
            QMessageBox.warning(self, "数量限制", f"自定义模板最多 {_MAX_CUSTOM_TEMPLATES} 个。")
            return

        name, ok = QInputDialog.getText(self, "新建模板", "请输入模板名称:")
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in self._get_all_template_names():
            QMessageBox.warning(self, "名称冲突", f'模板名称 "{name}" 已存在。')
            return

        self._save_editor_to_current_custom()
        self._custom_templates.append(
            {
                "name": name,
                "prompt": "You are a recognition assistant.\n\nAnalyze the provided image and output the recognized content.",
            }
        )
        self._populate_template_list()
        # Select the new template
        self._template_list.setCurrentRow(self._template_list.count() - 1)

    def _rename_custom_template(self) -> None:
        row = self._template_list.currentRow()
        if row < len(_PRESET_TEMPLATE_NAMES):
            return

        idx = row - len(_PRESET_TEMPLATE_NAMES)
        old_name = self._custom_templates[idx]["name"]

        new_name, ok = QInputDialog.getText(self, "重命名模板", "请输入新名称:", text=old_name)
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()

        if new_name == old_name:
            return

        if new_name in self._get_all_template_names():
            QMessageBox.warning(self, "名称冲突", f'模板名称 "{new_name}" 已存在。')
            return

        self._custom_templates[idx]["name"] = new_name

        # If the renamed template was the current one, update
        if self._current_template == old_name:
            self._current_template = new_name
            self._current_template_label.setText(f"当前: {new_name}")

        self._prev_selected_name = new_name
        self._populate_template_list()
        self._template_list.setCurrentRow(row)

    def _delete_custom_template(self) -> None:
        row = self._template_list.currentRow()
        if row < len(_PRESET_TEMPLATE_NAMES):
            return

        idx = row - len(_PRESET_TEMPLATE_NAMES)
        name = self._custom_templates[idx]["name"]

        reply = QMessageBox.question(
            self,
            "确认删除",
            f'确定要删除模板 "{name}" 吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._custom_templates.pop(idx)

        # If deleted template was the current one, reset to default
        if self._current_template == name:
            self._current_template = "智能识别"
            self._current_template_label.setText("当前: 智能识别")

        self._prev_selected_name = ""
        self._populate_template_list()

    def _set_template_as_current(self) -> None:
        row = self._template_list.currentRow()
        if row < 0:
            return

        item = self._template_list.item(row)
        name = item.data(Qt.ItemDataRole.UserRole)
        self._current_template = name
        self._current_template_label.setText(f"当前: {name}")

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
        self._endpoint_edit.setText(self._config.get("api.endpoint", "https://api.openai.com/v1"))
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
        self._auto_update_check.setChecked(bool(self._config.get("general.auto_update", True)))

        # Notification toggles
        self._notif_recognition.setChecked(
            bool(self._config.get("notifications.recognition_success", True))
        )
        self._notif_paste.setChecked(bool(self._config.get("notifications.paste_success", False)))
        self._notif_error.setChecked(bool(self._config.get("notifications.error", True)))

        self._screenshot_key_recorder.setHotkey(self._config.get("hotkeys.screenshot", "ctrl+shift+a"))
        self._paste_key_recorder.setHotkey(self._config.get("hotkeys.paste", "ctrl+shift+v"))

        # Templates
        self._current_template = self._config.get("templates.current", "智能识别")
        raw_custom = self._config.get("templates.custom", [])
        self._custom_templates = [
            {"name": t.get("name", ""), "prompt": t.get("prompt", "")}
            for t in raw_custom
            if isinstance(t, dict) and t.get("name")
        ]
        self._prev_selected_name = ""
        self._current_template_label.setText(f"当前: {self._current_template}")
        self._populate_template_list()

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

        # Notification toggles
        self._config.set("notifications.recognition_success", self._notif_recognition.isChecked())
        self._config.set("notifications.paste_success", self._notif_paste.isChecked())
        self._config.set("notifications.error", self._notif_error.isChecked())

        self._config.set("hotkeys.screenshot", self._screenshot_key_recorder.hotkey())
        self._config.set("hotkeys.paste", self._paste_key_recorder.hotkey())

        # Templates — save editor content for current custom template first
        self._save_editor_to_current_custom()
        self._config.set("templates.current", self._current_template)
        self._config.set("templates.custom", self._custom_templates)

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
        self._screenshot_key_recorder.setHotkey("ctrl+shift+a")
        self._paste_key_recorder.setHotkey("ctrl+shift+v")

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
            model=self._model_combo.currentText().strip(),
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

    @staticmethod
    def _load_icon() -> QIcon:
        """Load the TexPaste window icon."""
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "texpaste.ico"
        if icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon()

    # ------------------------------------------------------------------
    # About tab
    # ------------------------------------------------------------------

    def _build_about_tab(self) -> QWidget:
        """Build the About tab with version info, update check, and links."""
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)

        # Version info group
        version_group = QGroupBox("版本信息")
        version_layout = QVBoxLayout(version_group)

        current_version = self._config.get("version", "1.0.0")
        self._version_label = QLabel(f"当前版本: {current_version}")
        version_layout.addWidget(self._version_label)

        # Check update button
        self._check_update_btn = QPushButton("检查更新")
        self._check_update_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._check_update_btn.clicked.connect(self._check_for_update)
        version_layout.addWidget(self._check_update_btn)

        outer.addWidget(version_group)

        # Author info group
        author_group = QGroupBox("作者")
        author_layout = QVBoxLayout(author_group)
        author_layout.addWidget(QLabel("StoneLL1"))
        outer.addWidget(author_group)

        # Links group
        links_group = QGroupBox("链接")
        links_layout = QVBoxLayout(links_group)

        github_btn = QPushButton("GitHub 仓库")
        github_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        github_btn.clicked.connect(self._open_github)
        links_layout.addWidget(github_btn)

        outer.addWidget(links_group)
        outer.addStretch()
        return container

    def _check_for_update(self) -> None:
        """Trigger a manual update check."""
        self._check_update_btn.setEnabled(False)
        self._check_update_btn.setText("检查中...")

        self._update_checker = UpdateChecker(self._config, self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self._on_up_to_date)
        self._update_checker.check_failed.connect(self._on_update_check_failed)
        self._update_checker.check_once()

    def _on_update_available(self, latest_version: str, download_url: str) -> None:
        """Handle update available notification."""
        self._reset_update_btn()
        reply = QMessageBox.question(
            self,
            "发现新版本",
            f"请更新到最新版本 v{latest_version}\n\n是否打开下载页面？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(download_url)

    def _on_up_to_date(self) -> None:
        """Handle already up-to-date notification."""
        self._reset_update_btn()
        QMessageBox.information(self, "检查更新", "已是最新版本。")

    def _on_update_check_failed(self, error_msg: str) -> None:
        """Handle update check failure."""
        self._reset_update_btn()
        QMessageBox.warning(self, "检查更新失败", f"检查更新时出现错误：\n{error_msg}")

    def _reset_update_btn(self) -> None:
        """Reset the update check button to its default state."""
        self._check_update_btn.setEnabled(True)
        self._check_update_btn.setText("检查更新")

    def _open_github(self) -> None:
        """Open the GitHub repository page in the default browser."""
        webbrowser.open("https://github.com/StoneLL1/TexPaste")
