from __future__ import annotations

import httpx
from PyQt6.QtCore import QObject, QThread, pyqtSignal as Signal, pyqtSlot as Slot

from utils.config import ConfigManager
from utils.logger import get_logger

logger = get_logger(__name__)


class _UpdateWorker(QObject):
    """Background worker that fetches the GitHub Releases API and parses the response."""

    finished = Signal(str, str)  # (latest_version, download_url)
    failed = Signal(str)  # error message

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    @Slot()
    def run(self) -> None:
        """Perform the HTTP request and emit the result."""
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(self._url)
                response.raise_for_status()

            data: dict = response.json()
            tag_name: str = data.get("tag_name", "")
            html_url: str = data.get("html_url", "")

            if not tag_name:
                self.failed.emit("响应中未找到 tag_name 字段。")
                return

            # Strip leading 'v' from tag names like "v1.2.0"
            version = tag_name.lstrip("v")
            self.finished.emit(version, html_url)

        except httpx.TimeoutException:
            self.failed.emit("检查更新超时（10 秒），请检查网络连接。")
        except httpx.HTTPStatusError as exc:
            self.failed.emit(f"更新服务器返回错误：{exc.response.status_code}")
        except httpx.RequestError as exc:
            self.failed.emit(f"网络请求失败：{exc}")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"检查更新时发生未知错误：{exc}")


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints for comparison.

    Examples:
        "1.2.3" -> (1, 2, 3)
        "2.0"   -> (2, 0)
    """
    parts: list[int] = []
    for part in version_str.strip().split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


class UpdateChecker(QObject):
    """Checks GitHub Releases for a newer version of TexPaste.

    Usage::

        checker = UpdateChecker(config)
        checker.update_available.connect(lambda ver, url: ...)
        checker.check_once()
    """

    update_available = Signal(str, str)  # (latest_version, download_url)

    def __init__(
        self,
        config: ConfigManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._thread: QThread | None = None
        self._worker: _UpdateWorker | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_once(self) -> None:
        """Launch a one-shot background check against the configured URL.

        If a check is already in progress, the call is ignored.
        """
        if self._thread is not None and self._thread.isRunning():
            logger.debug("UpdateChecker: check already in progress, skipping.")
            return

        url: str = self._config.get("update.check_url", "")
        if not url:
            logger.info("UpdateChecker: update.check_url is empty — skipping update check.")
            return

        if not url.startswith(("http://", "https://")):
            logger.warning("UpdateChecker: update.check_url does not look like a valid URL: %s", url)
            return

        logger.info("UpdateChecker: checking for updates at %s", url)

        self._thread = QThread(self)
        self._worker = _UpdateWorker(url)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)

        # Tear down thread once the worker signals completion
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _on_worker_finished(self, latest_version: str, download_url: str) -> None:
        """Compare the fetched version with the current app version."""
        current_version: str = self._config.get("version", "1.0.0")
        logger.info(
            "UpdateChecker: current=%s  latest=%s", current_version, latest_version
        )

        try:
            if _parse_version(latest_version) > _parse_version(current_version):
                logger.info(
                    "UpdateChecker: new version available: %s  url=%s",
                    latest_version,
                    download_url,
                )
                self.update_available.emit(latest_version, download_url)
            else:
                logger.info("UpdateChecker: already up to date.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("UpdateChecker: version comparison failed: %s", exc)

    @Slot(str)
    def _on_worker_failed(self, error_msg: str) -> None:
        logger.warning("UpdateChecker: %s", error_msg)
