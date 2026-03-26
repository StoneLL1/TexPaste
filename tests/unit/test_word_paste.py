from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the src package is importable when running pytest from the project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# ---------------------------------------------------------------------------
# Stub heavy platform dependencies so the module can be imported on any OS
# ---------------------------------------------------------------------------
for _mod in (
    "win32gui",
    "win32process",
    "win32com",
    "win32com.client",
    "pythoncom",
    "psutil",
    "PyQt6",
    "PyQt6.QtCore",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Provide a minimal QObject / Signal stand-in so the import succeeds
import types

_qt_core = types.ModuleType("PyQt6.QtCore")
_qt_core.QObject = object  # type: ignore[attr-defined]

# Support both old (Signal) and new (pyqtSignal) names
_signal_mock = MagicMock(return_value=None)
_qt_core.Signal = _signal_mock  # type: ignore[attr-defined]
_qt_core.pyqtSignal = _signal_mock  # type: ignore[attr-defined]

sys.modules["PyQt6.QtCore"] = _qt_core
sys.modules["PyQt6"] = types.ModuleType("PyQt6")

import pytest  # noqa: E402

from models.enums import ContentType  # noqa: E402
from core.word_paste import (  # noqa: E402
    PandocConverter,
    WordPasteService,
    is_word_wps_active,
)


# ===========================================================================
# is_word_wps_active
# ===========================================================================


class TestIsWordWpsActive:
    """Tests for is_word_wps_active()."""

    def _make_psutil_mock(self, proc_name: str) -> MagicMock:
        process_mock = MagicMock()
        process_mock.name.return_value = proc_name
        psutil_mock = MagicMock()
        psutil_mock.Process.return_value = process_mock
        return psutil_mock

    def test_is_word_active_winword(self) -> None:
        """Foreground process WINWORD.EXE → (True, 'Word')."""
        # Create mock modules
        wg = MagicMock()
        wg.GetForegroundWindow.return_value = 1234
        wp = MagicMock()
        wp.GetWindowThreadProcessId.return_value = (0, 9999)
        psutil_mock = self._make_psutil_mock("WINWORD.EXE")

        with patch.dict("sys.modules", {"win32gui": wg, "win32process": wp, "psutil": psutil_mock}):
            result = is_word_wps_active()

        assert result == (True, "Word")

    def test_is_word_active_wps(self) -> None:
        """Foreground process wps.exe → (True, 'WPS')."""
        # Create mock modules
        wg = MagicMock()
        wg.GetForegroundWindow.return_value = 5678
        wp = MagicMock()
        wp.GetWindowThreadProcessId.return_value = (0, 1111)
        psutil_mock = self._make_psutil_mock("wps.exe")

        with patch.dict("sys.modules", {"win32gui": wg, "win32process": wp, "psutil": psutil_mock}):
            result = is_word_wps_active()

        assert result == (True, "WPS")

    def test_is_word_active_other(self) -> None:
        """Foreground process notepad.exe → (False, '')."""
        # Create mock modules
        wg = MagicMock()
        wg.GetForegroundWindow.return_value = 7890
        wp = MagicMock()
        wp.GetWindowThreadProcessId.return_value = (0, 2222)
        psutil_mock = self._make_psutil_mock("notepad.exe")

        with patch.dict("sys.modules", {"win32gui": wg, "win32process": wp, "psutil": psutil_mock}):
            result = is_word_wps_active()

        assert result == (False, "")


# ===========================================================================
# PandocConverter
# ===========================================================================


class TestPandocConverter:
    """Tests for PandocConverter.md_to_docx."""

    def test_pandoc_converter_runs_correct_args(self, tmp_path: Path) -> None:
        """Pandoc is called with the expected command-line arguments."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("core.word_paste.subprocess.run", return_value=mock_result) as mock_run:
            converter = PandocConverter(pandoc_path="pandoc")
            # Patch NamedTemporaryFile to control paths without actual disk writes
            fake_md = tmp_path / "fake.md"
            fake_md.write_text("# hello", encoding="utf-8")
            fake_docx = tmp_path / "fake.docx"
            fake_docx.write_bytes(b"")  # create so unlink works

            nm_mock = MagicMock()
            nm_mock.__enter__ = MagicMock(return_value=nm_mock)
            nm_mock.__exit__ = MagicMock(return_value=False)
            nm_mock.name = str(fake_md)

            with patch("core.word_paste.tempfile.NamedTemporaryFile", return_value=nm_mock):
                result_path = converter.md_to_docx("# hello")

        call_args = mock_run.call_args[0][0]  # first positional arg is the cmd list
        assert call_args[0] == "pandoc"
        assert "--from=markdown+tex_math_dollars" in call_args
        assert "--to=docx" in call_args
        assert "--mathml" in call_args
        # output flag
        assert "-o" in call_args

    def test_pandoc_converter_raises_on_error(self, tmp_path: Path) -> None:
        """RuntimeError is raised when Pandoc returns a non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some pandoc error"

        fake_md = tmp_path / "fake.md"
        fake_md.write_text("bad content", encoding="utf-8")

        nm_mock = MagicMock()
        nm_mock.__enter__ = MagicMock(return_value=nm_mock)
        nm_mock.__exit__ = MagicMock(return_value=False)
        nm_mock.name = str(fake_md)

        with (
            patch("core.word_paste.subprocess.run", return_value=mock_result),
            patch("core.word_paste.tempfile.NamedTemporaryFile", return_value=nm_mock),
        ):
            converter = PandocConverter()
            with pytest.raises(RuntimeError, match="Pandoc failed"):
                converter.md_to_docx("bad content")


# ===========================================================================
# WordPasteService
# ===========================================================================


class TestWordPasteService:
    """Tests for WordPasteService._do_paste via mocked COM."""

    def _make_com_mocks(self) -> tuple[MagicMock, MagicMock, MagicMock]:
        """Return (pythoncom_mock, win32com_mock, word_app_mock)."""
        pythoncom_mock = MagicMock()
        word_app_mock = MagicMock()
        win32com_mock = MagicMock()
        win32com_mock.client.GetActiveObject.return_value = word_app_mock
        return pythoncom_mock, win32com_mock, word_app_mock

    def test_paste_plain_text_calls_type_text(self) -> None:
        """PLAIN_TEXT content must call Selection.TypeText with the original string."""
        pythoncom_mock, win32com_mock, word_mock = self._make_com_mocks()
        selection_mock = MagicMock()
        word_mock.Selection = selection_mock

        with (
            patch.dict(
                sys.modules,
                {"pythoncom": pythoncom_mock, "win32com": win32com_mock,
                 "win32com.client": win32com_mock.client},
            ),
            patch("core.word_paste.WordPasteService._get_word_app", return_value=word_mock),
        ):
            service = WordPasteService()
            success, msg = service._do_paste("Hello world", ContentType.PLAIN_TEXT)

        assert success is True
        assert msg == "已插入文本"
        selection_mock.TypeText.assert_called_once_with("Hello world")

    def test_paste_latex_calls_pandoc(self) -> None:
        """PURE_LATEX content must be wrapped in $$ and passed to PandocConverter."""
        fake_docx = Path(tempfile.mktemp(suffix=".docx"))  # noqa: S306 — test only

        pythoncom_mock, win32com_mock, word_mock = self._make_com_mocks()
        selection_mock = MagicMock()
        word_mock.Selection = selection_mock

        converter_mock = MagicMock()
        converter_mock.md_to_docx.return_value = fake_docx

        tmp_doc_mock = MagicMock()
        word_mock.Documents.Open.return_value = tmp_doc_mock

        with (
            patch.dict(
                sys.modules,
                {"pythoncom": pythoncom_mock, "win32com": win32com_mock,
                 "win32com.client": win32com_mock.client},
            ),
            patch("core.word_paste.WordPasteService._get_word_app", return_value=word_mock),
            patch("core.word_paste.PandocConverter", return_value=converter_mock),
        ):
            service = WordPasteService()
            success, msg = service._do_paste(r"\frac{1}{2}", ContentType.PURE_LATEX)

        # Pandoc must receive the LaTeX wrapped in $$…$$
        converter_mock.md_to_docx.assert_called_once_with(r"$$\frac{1}{2}$$")
        assert success is True
        assert msg == "已插入公式"


import tempfile  # noqa: E402  (imported here to avoid top-level side-effects in stubs)
