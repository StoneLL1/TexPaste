from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import QObject
from PyQt6.QtCore import pyqtSignal as Signal

from models.enums import ContentType
from utils.logger import get_logger

logger = get_logger("word_paste")


def is_word_wps_active() -> tuple[bool, str]:
    """Return (True, app_name) if the foreground window belongs to Word or WPS."""
    try:
        import psutil
        import win32gui
        import win32process
    except ImportError:
        logger.warning("pywin32/psutil not available — is_word_wps_active always returns False")
        return False, ""

    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            proc_name = psutil.Process(pid).name().lower()
            if "winword" in proc_name:
                return True, "Word"
            if "wps" in proc_name or "et" in proc_name:
                return True, "WPS"
        except psutil.NoSuchProcess:
            pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("is_word_wps_active: unexpected error: %s", exc)

    return False, ""


class PandocConverter:
    """Convert Markdown (with TeX math) to a temporary .docx file via Pandoc."""

    def __init__(self, pandoc_path: str = "pandoc") -> None:
        self.pandoc_path = pandoc_path

    def md_to_docx(self, markdown_content: str) -> Path:
        """Write *markdown_content* to a temp file, run Pandoc, return the .docx Path.

        Raises RuntimeError if Pandoc exits with a non-zero return code.
        The caller is responsible for deleting the returned .docx file.
        """
        # Write Markdown to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as md_file:
            md_file.write(markdown_content)
            md_path = Path(md_file.name)

        docx_path = md_path.with_suffix(".docx")
        try:
            result = subprocess.run(
                [
                    self.pandoc_path,
                    str(md_path),
                    "-o",
                    str(docx_path),
                    "--from=markdown+tex_math_dollars",
                    "--to=docx",
                    "--mathml",
                ],
                capture_output=True,
                text=True,
            )
        finally:
            md_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(f"Pandoc failed (exit {result.returncode}): {result.stderr.strip()}")

        return docx_path


class WordPasteService:
    """Paste recognised content into the active Word/WPS document via COM."""

    def __init__(self, pandoc_path: str = "pandoc") -> None:
        self._pandoc_path = pandoc_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def paste(self, content: str, content_type: ContentType) -> tuple[bool, str]:
        """CoInitialize COM, delegate to _do_paste, CoUninitialize in finally."""
        try:
            import pythoncom
        except ImportError:
            logger.warning("pythoncom not available — Word paste disabled")
            return False, "pywin32 not available"

        pythoncom.CoInitialize()
        try:
            return self._do_paste(content, content_type)
        finally:
            pythoncom.CoUninitialize()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_word_app(self) -> object | None:
        """Return an active Word or WPS COM application object, or None."""
        try:
            import win32com.client
        except ImportError:
            return None

        for prog_id in ("Word.Application", "Kwps.Application"):
            try:
                return win32com.client.GetActiveObject(prog_id)
            except Exception:  # noqa: BLE001
                continue
        return None

    def _do_paste(self, content: str, content_type: ContentType) -> tuple[bool, str]:
        """Insert *content* at the current cursor position in Word/WPS."""
        word = self._get_word_app()
        if word is None:
            logger.error("_do_paste: no Word/WPS instance found")
            return False, "未找到 Word/WPS 实例"

        selection = word.Selection

        if content_type is ContentType.PLAIN_TEXT:
            selection.TypeText(content)
            logger.info("_do_paste: inserted plain text (%d chars)", len(content))
            return True, "已插入文本"

        converter = PandocConverter(pandoc_path=self._pandoc_path)

        if content_type is ContentType.PURE_LATEX:
            markdown_content = f"$${content}$$"
        else:
            # ContentType.MARKDOWN
            markdown_content = content

        try:
            docx_path = converter.md_to_docx(markdown_content)
        except RuntimeError as exc:
            logger.error("_do_paste: Pandoc conversion failed: %s", exc)
            return False, f"Pandoc 转换失败: {exc}"

        return self._insert_docx(word, selection, docx_path)

    def _insert_docx(self, word: object, selection: object, docx_path: Path) -> tuple[bool, str]:
        """Open *docx_path* via COM, copy its content, paste at *selection*, then close."""
        tmp_doc = None
        try:
            tmp_doc = word.Documents.Open(str(docx_path))
            tmp_doc.Content.Copy()
            selection.Paste()
            logger.info("_insert_docx: pasted content from %s", docx_path)
            return True, "已插入公式"
        except Exception as exc:  # noqa: BLE001
            logger.error("_insert_docx: COM error: %s", exc)
            return False, f"COM 插入失败: {exc}"
        finally:
            if tmp_doc is not None:
                try:
                    tmp_doc.Close(False)
                except Exception:  # noqa: BLE001
                    pass
            docx_path.unlink(missing_ok=True)


class WordPasteWorker(QObject):
    """QThread-compatible worker that runs WordPasteService on a background thread."""

    paste_complete: Signal = Signal(bool, str)  # (success, message)

    def __init__(
        self,
        content: str,
        content_type: ContentType,
        pandoc_path: str = "pandoc",
    ) -> None:
        super().__init__()
        self._content = content
        self._content_type = content_type
        self._pandoc_path = pandoc_path

    def run(self) -> None:
        """Execute the paste operation and emit paste_complete when finished."""
        success, message = WordPasteService(pandoc_path=self._pandoc_path).paste(
            self._content, self._content_type
        )
        self.paste_complete.emit(success, message)
