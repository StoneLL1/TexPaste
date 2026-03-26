from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models.enums import AppState, ContentType
from models.history import HistoryRecord


def test_content_type_values() -> None:
    assert ContentType.PLAIN_TEXT == "text"
    assert ContentType.PURE_LATEX == "latex"
    assert ContentType.MARKDOWN == "markdown"


def test_content_type_is_str() -> None:
    assert isinstance(ContentType.PLAIN_TEXT, str)


def test_app_state_values() -> None:
    assert AppState.IDLE == "idle"
    assert AppState.CAPTURING == "capturing"
    assert AppState.RECOGNIZING == "recognizing"
    assert AppState.PASTING == "pasting"


def test_history_record_instantiation() -> None:
    record = HistoryRecord(
        id=1,
        created_at="2026-03-26T00:00:00",
        content_type="latex",
        result=r"\frac{1}{2}",
    )
    assert record.id == 1
    assert record.thumbnail is None
    assert record.api_model is None


def test_history_record_with_thumbnail() -> None:
    record = HistoryRecord(
        id=2,
        created_at="2026-03-26T00:00:00",
        content_type="text",
        result="Hello world",
        thumbnail=b"\x89PNG",
        api_model="gpt-4o",
    )
    assert record.thumbnail == b"\x89PNG"
    assert record.api_model == "gpt-4o"
