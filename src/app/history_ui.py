from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.clipboard import ClipboardManager
from models.history import HistoryRecord
from utils.db import HistoryRepository
from utils.logger import get_logger

logger = get_logger(__name__)

CONTENT_TYPE_BADGES: dict[str, str] = {
    "text": "文本",
    "latex": "公式",
    "markdown": "混合",
}


class HistoryUI(QDialog):
    """Dialog window for viewing and managing recognition history records."""

    def __init__(
        self,
        history_repo: HistoryRepository,
        clipboard: ClipboardManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._repo = history_repo
        self._clipboard = clipboard
        self._records: list[HistoryRecord] = []
        self._selected_record: HistoryRecord | None = None
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search_timer_fired)

        self._setup_ui()
        self._load_history()

    def _setup_ui(self) -> None:
        """Build and arrange all UI widgets."""
        self.setWindowTitle("TexPaste 历史记录")
        self.setMinimumSize(600, 400)
        self.resize(800, 500)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # --- Top bar: search + clear-all ---
        top_layout = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("搜索...")
        self._search_edit.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_edit)

        self._clear_all_btn = QPushButton("清除全部")
        self._clear_all_btn.clicked.connect(self._on_clear_all_clicked)
        top_layout.addWidget(self._clear_all_btn)
        root_layout.addLayout(top_layout)

        # --- Center: splitter with list + detail pane ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._list_widget = QListWidget()
        self._list_widget.setMinimumWidth(200)
        self._list_widget.setSizeHint = lambda: self._list_widget.sizeHint()  # type: ignore[method-assign]
        self._list_widget.currentRowChanged.connect(self._on_item_selected)
        splitter.addWidget(self._list_widget)

        self._detail_edit = QTextEdit()
        self._detail_edit.setReadOnly(True)
        splitter.addWidget(self._detail_edit)

        splitter.setSizes([250, 550])
        root_layout.addWidget(splitter, stretch=1)

        # --- Bottom bar: copy + close ---
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self._copy_btn = QPushButton("复制")
        self._copy_btn.clicked.connect(self._on_copy_clicked)
        bottom_layout.addWidget(self._copy_btn)

        self._close_btn = QPushButton("关闭")
        self._close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self._close_btn)

        root_layout.addLayout(bottom_layout)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_history(self, query: str = "") -> None:
        """Fetch records from the repository and populate the list widget."""
        try:
            if query:
                records = self._repo.search(query)
            else:
                records = self._repo.list(limit=100)
        except Exception:
            logger.exception("Failed to load history records")
            records = []

        self._records = list(records)
        self._list_widget.clear()
        self._selected_record = None
        self._detail_edit.clear()

        for record in self._records:
            badge = CONTENT_TYPE_BADGES.get(record.content_type, record.content_type)
            timestamp = record.created_at[:16] if record.created_at else ""
            preview = record.result[:50]
            item_text = f"[{badge}] {timestamp}  {preview}"
            self._list_widget.addItem(QListWidgetItem(item_text))

        logger.info("Loaded %d history records (query=%r)", len(self._records), query)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_selected(self, row: int) -> None:
        """Display full result text for the selected list item."""
        if row < 0 or row >= len(self._records):
            self._selected_record = None
            self._detail_edit.clear()
            return

        self._selected_record = self._records[row]
        self._detail_edit.setPlainText(self._selected_record.result)

    def _on_copy_clicked(self) -> None:
        """Copy the selected record's result to the clipboard."""
        if self._selected_record is None:
            return

        try:
            self._clipboard.set_text(self._selected_record.result)
            self._copy_btn.setText("已复制!")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("复制"))
            logger.info("Copied history record to clipboard")
        except Exception:
            logger.exception("Failed to copy record to clipboard")

    def _on_clear_all_clicked(self) -> None:
        """Prompt the user and delete all history records on confirmation."""
        answer = QMessageBox.question(
            self,
            "确认清除",
            "确定要删除全部历史记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            conn = self._repo._get_conn()
            conn.execute("DELETE FROM history")
            conn.commit()
            logger.info("All history records deleted")
        except Exception:
            logger.exception("Failed to delete all history records")
            QMessageBox.warning(self, "错误", "删除历史记录时发生错误，请查看日志。")
            return

        self._load_history(self._search_edit.text())

    def _on_search_changed(self, text: str) -> None:
        """Restart the debounce timer whenever the search text changes."""
        self._search_timer.start()

    def _on_search_timer_fired(self) -> None:
        """Execute the debounced search."""
        self._load_history(self._search_edit.text())
