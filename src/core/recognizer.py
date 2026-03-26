from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

import httpx
from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal, pyqtSlot as Slot

from core.clipboard import detect_content_type
from utils.config import ConfigManager
from utils.logger import get_logger

logger = get_logger("core.recognizer")

_PROMPT_PATH = Path(__file__).parent.parent / "resources" / "prompts" / "recognize.txt"


class RecognitionWorker(QObject):
    """Worker that runs LLM API recognition in a background QThread."""

    finished = Signal(str, str)  # (result, content_type_value)
    failed = Signal(str)  # (error_message)

    def __init__(self, image_bytes: bytes, config: dict[str, Any]) -> None:
        super().__init__()
        self._image_bytes = image_bytes
        self._config = config

    @Slot()
    def run(self) -> None:
        """Entry point called by QThread.started signal."""
        max_retries: int = self._config.get("max_retries", 3)
        delays = [2**i for i in range(max_retries)]  # 1s, 2s, 4s for retries 0,1,2

        last_error: str = "未知错误"

        for attempt in range(max_retries):
            try:
                result = asyncio.run(self._call_api())
                content_type = detect_content_type(result)
                logger.info(
                    "Recognition succeeded on attempt %d, content_type=%s",
                    attempt + 1,
                    content_type.value,
                )
                self.finished.emit(result, content_type.value)
                return

            except httpx.TimeoutException:
                last_error = "请求超时，请检查网络连接"
                logger.warning("Recognition attempt %d timed out", attempt + 1)
                # Retry on timeout

            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if 400 <= status < 500:
                    # 4xx — do not retry
                    error_msg = f"API 错误：{status}"
                    logger.error("HTTP %d error, will not retry", status)
                    self.failed.emit(error_msg)
                    return
                else:
                    # 5xx — retryable
                    last_error = f"API 错误：{status}"
                    logger.warning("HTTP %d error on attempt %d", status, attempt + 1)

            except Exception as exc:
                # Network / other errors — retryable
                last_error = f"网络错误：{type(exc).__name__}"
                logger.warning("Network error on attempt %d: %s", attempt + 1, type(exc).__name__)

            # Exponential backoff before next retry (skip sleep after last attempt)
            if attempt < max_retries - 1:
                import time

                time.sleep(delays[attempt])

        logger.error("All %d recognition attempts failed. Last error: %s", max_retries, last_error)
        self.failed.emit(last_error)

    async def _call_api(self) -> str:
        """Encode image and POST to the LLM API, returning the response text."""
        b64 = base64.b64encode(self._image_bytes).decode("ascii")

        try:
            system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        except OSError:
            logger.error("Could not read prompt file: %s", _PROMPT_PATH)
            system_prompt = "You are a LaTeX/text recognition assistant."

        endpoint: str = self._config["endpoint"].rstrip("/")
        model: str = self._config["model"]
        timeout: float = float(self._config.get("timeout", 30))

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "识别图片内容"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ],
            "max_tokens": 4096,
        }

        # NOTE: API key is never logged — only used in the Authorization header.
        headers = {
            "Authorization": f"Bearer {self._config['api_key']}",
            "Content-Type": "application/json",
        }

        logger.debug("Sending recognition request to %s/chat/completions (model=%s)", endpoint, model)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{endpoint}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

        return resp.json()["choices"][0]["message"]["content"]


class RecognizerService(QObject):
    """High-level service that manages RecognitionWorker lifecycle on a QThread."""

    recognition_complete = Signal(str, str)  # (result, content_type_value)
    recognition_failed = Signal(str)  # (error_message)
    recognition_progress = Signal(str)  # (status_text)

    def __init__(self, config: ConfigManager, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._cancelled: bool = False
        # Keep references to prevent GC while threads are running
        self._active_threads: list[QThread] = []
        self._active_workers: list[RecognitionWorker] = []

    def recognize(self, image_bytes: bytes) -> None:
        """Start an async recognition job for *image_bytes*."""
        self._cancelled = False

        config_dict: dict[str, Any] = {
            "endpoint": self._config.get("api.endpoint", ""),
            "api_key": self._config.get("api.key", ""),
            "model": self._config.get("api.model", "gpt-4o"),
            "timeout": self._config.get("api.timeout", 30),
            "max_retries": self._config.get("api.max_retries", 3),
        }

        thread = QThread()
        worker = RecognitionWorker(image_bytes, config_dict)
        worker.moveToThread(thread)

        # Wire up signals
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(worker.deleteLater)

        # Cleanup our references when the thread is done
        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))

        # Store refs so Python GC doesn't collect them before the thread finishes
        self._active_threads.append(thread)
        self._active_workers.append(worker)

        self.recognition_progress.emit("正在识别...")
        logger.info("Starting recognition thread")
        thread.start()

    def cancel(self) -> None:
        """Signal that the current recognition should be abandoned."""
        self._cancelled = True
        logger.info("Recognition cancelled by caller")

    @Slot(str, str)
    def _on_worker_finished(self, result: str, content_type_value: str) -> None:
        if self._cancelled:
            logger.info("Recognition finished but was cancelled — suppressing result")
            return
        self.recognition_complete.emit(result, content_type_value)

    @Slot(str)
    def _on_worker_failed(self, error: str) -> None:
        if self._cancelled:
            logger.info("Recognition failed but was cancelled — suppressing error")
            return
        self.recognition_failed.emit(error)

    def _cleanup_thread(self, thread: QThread, worker: RecognitionWorker) -> None:
        """Remove finished thread/worker from tracking lists."""
        try:
            self._active_threads.remove(thread)
        except ValueError:
            pass
        try:
            self._active_workers.remove(worker)
        except ValueError:
            pass
