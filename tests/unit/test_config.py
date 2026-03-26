from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.config import ConfigManager


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    return tmp_path / "config.json"


@pytest.fixture()
def mgr(tmp_config: Path) -> ConfigManager:
    return ConfigManager(tmp_config)


# ------------------------------------------------------------------
# deep_merge
# ------------------------------------------------------------------


def test_deep_merge_simple() -> None:
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}}
    result = ConfigManager._deep_merge(base, override)
    assert result["a"] == 1
    assert result["b"]["c"] == 99
    assert result["b"]["d"] == 3


def test_deep_merge_new_key() -> None:
    base = {"a": 1}
    override = {"b": 2}
    result = ConfigManager._deep_merge(base, override)
    assert result["b"] == 2
    assert result["a"] == 1


def test_deep_merge_override_dict_with_scalar() -> None:
    base = {"a": {"b": 1}}
    override = {"a": "flat"}
    result = ConfigManager._deep_merge(base, override)
    assert result["a"] == "flat"


# ------------------------------------------------------------------
# get / set
# ------------------------------------------------------------------


def test_get_default_value(mgr: ConfigManager) -> None:
    # Should return default config value (api.endpoint)
    assert mgr.get("api.endpoint") == "https://api.openai.com/v1"


def test_get_missing_key_returns_default(mgr: ConfigManager) -> None:
    assert mgr.get("does.not.exist", "fallback") == "fallback"


def test_set_and_get_roundtrip(mgr: ConfigManager, tmp_config: Path) -> None:
    mgr.set("api.api_key", "sk-test-123")
    assert mgr.get("api.api_key") == "sk-test-123"


def test_set_persists_to_disk(mgr: ConfigManager, tmp_config: Path) -> None:
    mgr.set("api.model", "claude-3-5-sonnet")
    data = json.loads(tmp_config.read_text())
    assert data["api"]["model"] == "claude-3-5-sonnet"


def test_set_nested_path_creates_keys(mgr: ConfigManager) -> None:
    mgr.set("new.nested.key", 42)
    assert mgr.get("new.nested.key") == 42


# ------------------------------------------------------------------
# reload
# ------------------------------------------------------------------


def test_reload_picks_up_disk_changes(tmp_config: Path) -> None:
    mgr = ConfigManager(tmp_config)
    mgr.set("api.model", "first-model")

    # Simulate external edit
    data = json.loads(tmp_config.read_text())
    data["api"]["model"] = "second-model"
    tmp_config.write_text(json.dumps(data))

    mgr.reload()
    assert mgr.get("api.model") == "second-model"


# ------------------------------------------------------------------
# defaults fallback
# ------------------------------------------------------------------


def test_defaults_loaded_when_no_user_config(tmp_config: Path) -> None:
    mgr = ConfigManager(tmp_config)
    assert mgr.get("hotkeys.screenshot") == "ctrl+shift+a"
    assert mgr.get("hotkeys.paste") == "ctrl+shift+v"
    assert mgr.get("history.retention_days") == 7
