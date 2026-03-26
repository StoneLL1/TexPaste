from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_app_data_dir() -> Path:
    """Return app data directory.

    Portable mode: exe directory (when .portable marker exists).
    Installed mode: %APPDATA%/TexPaste.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent.parent.parent

    portable_flag = exe_dir / ".portable"
    if portable_flag.exists():
        return exe_dir

    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "TexPaste"
    return exe_dir / "data"


def setup_logger(log_dir: Path) -> logging.Logger:
    """Configure rotating file logger for TexPaste."""
    log_dir.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_dir / "texpaste.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)

    logger = logging.getLogger("texpaste")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(console_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger under the texpaste namespace."""
    return logging.getLogger(f"texpaste.{name}")
