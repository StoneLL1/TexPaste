from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger("config")

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.default.json"


class ConfigManager:
    """Read/write configuration with dot-notation access and deep-merge defaults."""

    def __init__(self, config_path: Path) -> None:
        self._path = config_path
        self._data: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Read a value using dot-separated key path, e.g. 'api.endpoint'."""
        keys = key.split(".")
        val: Any = self._data
        for k in keys:
            if not isinstance(val, dict) or k not in val:
                return default
            val = val[k]
        return val

    def set(self, key: str, value: Any) -> None:
        """Write a value using dot-separated key path and persist to disk."""
        keys = key.split(".")
        d: dict[str, Any] = self._data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self._save()

    def reload(self) -> None:
        """Re-read configuration from disk."""
        self._load()

    def all(self) -> dict[str, Any]:
        """Return a shallow copy of the full configuration dict."""
        return dict(self._data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            defaults = json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.error("Failed to read default config", exc_info=True)
            defaults = {}

        if self._path.exists():
            try:
                user = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = self._deep_merge(defaults, user)
            except Exception:
                logger.error("Failed to read user config, using defaults", exc_info=True)
                self._data = defaults
        else:
            self._data = defaults

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.error("Failed to save config", exc_info=True)

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = base.copy()
        for k, v in override.items():
            if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = ConfigManager._deep_merge(result[k], v)
            else:
                result[k] = v
        return result
