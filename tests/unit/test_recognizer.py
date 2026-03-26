from __future__ import annotations

import asyncio
import logging
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# ---------------------------------------------------------------------------
# Stub PyQt6 before importing any core modules that use it
# ---------------------------------------------------------------------------
_qt_core = types.ModuleType("PyQt6.QtCore")
_qt_core.QObject = object  # type: ignore[attr-defined]
_qt_core.QThread = object  # type: ignore[attr-defined]

# No-op decorator for both old (Slot) and new (pyqtSlot) names
_slot_decorator = lambda *a, **kw: (lambda f: f)
_qt_core.Slot = _slot_decorator  # type: ignore[attr-defined]
_qt_core.pyqtSlot = _slot_decorator  # type: ignore[attr-defined]


class _Signal:
    """Minimal Signal stand-in: connect() and emit() work but do nothing by default."""

    def __init__(self, *types_: Any) -> None:
        self._callbacks: list[Any] = []

    def connect(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Any | None = None) -> None:
        if callback is None:
            self._callbacks.clear()
        else:
            self._callbacks = [c for c in self._callbacks if c is not callback]

    def emit(self, *args: Any) -> None:
        for cb in self._callbacks:
            cb(*args)


# Support both old (Signal) and new (pyqtSignal) names
_qt_core.Signal = _Signal  # type: ignore[attr-defined]
_qt_core.pyqtSignal = _Signal  # type: ignore[attr-defined]

# Create PyQt6.QtWidgets module for QApplication
_qt_widgets = types.ModuleType("PyQt6.QtWidgets")
_qt_widgets.QApplication = MagicMock()  # type: ignore[attr-defined]

# Create PyQt6 package module
_qt_pkg = types.ModuleType("PyQt6")
_qt_pkg.QtCore = _qt_core  # type: ignore[attr-defined]
_qt_pkg.QtWidgets = _qt_widgets  # type: ignore[attr-defined]

sys.modules["PyQt6"] = _qt_pkg  # type: ignore[assignment]
sys.modules["PyQt6.QtCore"] = _qt_core  # type: ignore[assignment]
sys.modules["PyQt6.QtWidgets"] = _qt_widgets  # type: ignore[assignment]

import httpx  # noqa: E402 (after sys.modules patching)

from core.recognizer import RecognitionWorker  # noqa: E402
from models.enums import ContentType  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "endpoint": "https://api.example.com/v1",
        "api_key": "sk-secret-key-do-not-log",
        "model": "gpt-4o",
        "timeout": 5,
        "max_retries": 3,
    }
    base.update(overrides)
    return base


def _make_api_response(content: str) -> MagicMock:
    """Build a mock httpx.Response that looks like a successful LLM response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _collect_signals(worker: RecognitionWorker) -> dict[str, list[tuple[Any, ...]]]:
    """Connect to worker signals and collect emitted values."""
    received: dict[str, list[tuple[Any, ...]]] = {"finished": [], "failed": []}
    worker.finished.connect(lambda r, ct: received["finished"].append((r, ct)))
    worker.failed.connect(lambda e: received["failed"].append((e,)))
    return received


# ---------------------------------------------------------------------------
# Test 1 — success path: finished signal with correct content type
# ---------------------------------------------------------------------------


class TestWorkerEmitsFinishedOnSuccess:
    @pytest.mark.parametrize(
        "api_content,expected_ct",
        [
            ("Hello world", ContentType.PLAIN_TEXT.value),
            (r"\frac{-b \pm \sqrt{b^2-4ac}}{2a}", ContentType.PURE_LATEX.value),
            ("The formula $E = mc^2$ is famous.", ContentType.MARKDOWN.value),
        ],
    )
    def test_finished_signal_with_content_type(
        self, api_content: str, expected_ct: str
    ) -> None:
        worker = RecognitionWorker(b"fake-image-bytes", _make_config())
        received = _collect_signals(worker)
        mock_resp = _make_api_response(api_content)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client
            worker.run()

        assert len(received["finished"]) == 1, "finished signal should be emitted once"
        assert len(received["failed"]) == 0, "failed signal must not be emitted"
        result, ct_value = received["finished"][0]
        assert result == api_content
        assert ct_value == expected_ct


# ---------------------------------------------------------------------------
# Test 2 — timeout: failed signal with "超时" message
# ---------------------------------------------------------------------------


class TestWorkerEmitsFailedOnTimeout:
    def test_failed_signal_on_timeout(self) -> None:
        worker = RecognitionWorker(b"fake-image-bytes", _make_config(max_retries=1))
        received = _collect_signals(worker)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
            mock_client_cls.return_value = mock_client
            worker.run()

        assert len(received["failed"]) == 1
        assert len(received["finished"]) == 0
        error_msg: str = received["failed"][0][0]
        assert "超时" in error_msg, f"Expected '超时' in error message, got: {error_msg!r}"

    def test_failed_message_exact_wording(self) -> None:
        worker = RecognitionWorker(b"bytes", _make_config(max_retries=1))
        received = _collect_signals(worker)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("connect timeout"))
            mock_client_cls.return_value = mock_client
            worker.run()

        assert received["failed"][0][0] == "请求超时，请检查网络连接"


# ---------------------------------------------------------------------------
# Test 3 — 4xx: no retry, called exactly once
# ---------------------------------------------------------------------------


class TestWorkerNoRetryOn4xx:
    def test_no_retry_on_400(self) -> None:
        worker = RecognitionWorker(b"bytes", _make_config(max_retries=3))
        received = _collect_signals(worker)

        mock_400_resp = MagicMock(spec=httpx.Response)
        mock_400_resp.status_code = 400
        http_error = httpx.HTTPStatusError("400 Bad Request", request=MagicMock(),
                                           response=mock_400_resp)
        call_count = 0

        async def _post_side_effect(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise http_error

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=_post_side_effect)
            mock_client_cls.return_value = mock_client
            worker.run()

        assert call_count == 1, f"API called {call_count} times, expected 1"
        assert len(received["failed"]) == 1
        assert len(received["finished"]) == 0
        assert "400" in received["failed"][0][0]

    @pytest.mark.parametrize("status_code", [401, 403, 422])
    def test_no_retry_on_various_4xx(self, status_code: int) -> None:
        worker = RecognitionWorker(b"bytes", _make_config(max_retries=3))
        received = _collect_signals(worker)

        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = status_code
        http_error = httpx.HTTPStatusError(f"{status_code}", request=MagicMock(),
                                           response=mock_resp)
        call_count = 0

        async def _raise(*args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            raise http_error

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=_raise)
            mock_client_cls.return_value = mock_client
            worker.run()

        assert call_count == 1, f"No retry expected for HTTP {status_code}"


# ---------------------------------------------------------------------------
# Test 4 — API key must NOT appear in log output
# ---------------------------------------------------------------------------


class TestApiKeyNotLogged:
    def test_api_key_not_in_log_on_success(self, caplog: pytest.LogCaptureFixture) -> None:
        secret_key = "sk-super-secret-key-12345"
        worker = RecognitionWorker(b"bytes", _make_config(api_key=secret_key))
        mock_resp = _make_api_response("plain text result")

        with caplog.at_level(logging.DEBUG, logger="texpaste"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client
                worker.run()

        for record in caplog.records:
            assert secret_key not in record.getMessage()

    def test_api_key_not_in_log_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        secret_key = "sk-another-secret-key-99999"
        worker = RecognitionWorker(b"bytes", _make_config(api_key=secret_key, max_retries=1))

        with caplog.at_level(logging.DEBUG, logger="texpaste"):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
                mock_client_cls.return_value = mock_client
                worker.run()

        for record in caplog.records:
            assert secret_key not in record.getMessage()
