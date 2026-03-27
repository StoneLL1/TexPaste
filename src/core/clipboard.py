from __future__ import annotations

import re

from PyQt6.QtWidgets import QApplication

from models.enums import ContentType
from utils.logger import get_logger

logger = get_logger("core.clipboard")


def detect_content_type(text: str) -> ContentType:
    """Detect the content type of the given text string.

    Returns ContentType.MARKDOWN if the text contains inline/display math formulas or
    Markdown syntax characters. Returns ContentType.PURE_LATEX if the text looks like
    raw LaTeX commands. Otherwise returns ContentType.PLAIN_TEXT.
    """
    has_inline_formula: bool = bool(re.search(r"\$.+?\$", text))
    has_display_formula: bool = bool(re.search(r"\$\$.+?\$\$", text, re.DOTALL))
    has_markdown_syntax: bool = bool(re.search(r"[#*`\[\]\|]", text))
    looks_like_latex: bool = bool(re.search(r"\\[a-zA-Z]+\{", text))

    if has_inline_formula or has_display_formula or has_markdown_syntax:
        return ContentType.MARKDOWN
    elif looks_like_latex:
        return ContentType.PURE_LATEX
    else:
        return ContentType.PLAIN_TEXT


class ClipboardManager:
    """Thin wrapper around Qt's clipboard providing typed read/write access."""

    def __init__(self) -> None:
        self._logger = get_logger("core.clipboard.manager")

    def set_text(self, text: str) -> None:
        """Write *text* to the system clipboard.

        Requires a running QApplication instance.
        """
        clipboard = QApplication.clipboard()
        if clipboard is None:
            self._logger.error("set_text called but QApplication clipboard is unavailable")
            return
        clipboard.setText(text)
        self._logger.debug("Clipboard updated (%d chars, type=%s)", len(text), detect_content_type(text))

    def get_text(self) -> str:
        """Read and return the current plain-text contents of the system clipboard.

        Returns an empty string when the clipboard contains no text or when the
        QApplication clipboard is unavailable.
        """
        clipboard = QApplication.clipboard()
        if clipboard is None:
            self._logger.error("get_text called but QApplication clipboard is unavailable")
            return ""
        text: str = clipboard.text()
        self._logger.debug("Clipboard read (%d chars)", len(text))
        return text
