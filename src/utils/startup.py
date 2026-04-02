from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("startup")

# Named mutex to prevent duplicate instances
_MUTEX_NAME = "Global\\TexPaste_SingleInstance"


class StartupError:
    def __init__(self, code: str, message: str, fatal: bool = True) -> None:
        self.code = code
        self.message = message
        self.fatal = fatal


class StartupChecker:
    """Run pre-launch environment checks."""

    def __init__(self, config_path: Path, pandoc_executable: str = "pandoc") -> None:
        self._config_path = config_path
        self._pandoc_executable = pandoc_executable
        self._mutex_handle: object = None

    def check_all(self) -> list[StartupError]:
        checks = [
            self._check_single_instance(),
            self._check_pandoc(),
            self._check_config(),
        ]
        return [e for e in checks if e is not None]

    def _check_single_instance(self) -> StartupError | None:
        try:
            import win32api
            import win32event

            handle = win32event.CreateMutex(None, True, _MUTEX_NAME)
            last_error = win32api.GetLastError()
            if last_error == 183:  # ERROR_ALREADY_EXISTS
                return StartupError(
                    "DUPLICATE_INSTANCE",
                    "TexPaste 已在运行中。请检查系统托盘。",
                    fatal=True,
                )
            self._mutex_handle = handle  # keep alive
            return None
        except ImportError:
            # pywin32 not available (dev/test env)
            logger.warning("pywin32 not available, skipping single-instance check")
            return None
        except Exception:
            logger.error("Single-instance check failed", exc_info=True)
            return None

    def _check_pandoc(self) -> StartupError | None:
        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                [self._pandoc_executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=creationflags,
            )
            if result.returncode == 0:
                version_line = result.stdout.split("\n")[0]
                logger.info("Pandoc found: %s", version_line)
                return None
            return StartupError(
                "PANDOC_ERROR",
                "Pandoc 运行失败，Word/WPS 智能粘贴功能不可用。",
                fatal=False,
            )
        except FileNotFoundError:
            return StartupError(
                "PANDOC_NOT_FOUND",
                (
                    "未找到 Pandoc。Word/WPS 智能粘贴功能不可用。\n"
                    "请从 https://pandoc.org/installing.html 安装 Pandoc。"
                ),
                fatal=False,
            )
        except Exception:
            logger.error("Pandoc check failed", exc_info=True)
            return None

    def _check_config(self) -> StartupError | None:
        if not self._config_path.exists():
            return None  # Missing user config is fine — defaults will be used
        try:
            json.loads(self._config_path.read_text(encoding="utf-8"))
            return None
        except json.JSONDecodeError as e:
            return StartupError(
                "CONFIG_CORRUPT",
                f"配置文件损坏，无法解析：{e}\n请删除 config.json 以恢复默认配置。",
                fatal=True,
            )
        except Exception:
            logger.error("Config check failed", exc_info=True)
            return None
