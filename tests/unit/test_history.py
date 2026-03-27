from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from utils.db import HistoryRepository


@pytest.fixture()
def repo(tmp_path: Path) -> HistoryRepository:
    """In-memory SQLite repo for isolated tests."""
    db_path = tmp_path / "test_history.db"
    r = HistoryRepository(db_path)
    yield r
    r.close()


def test_save_and_count(repo: HistoryRepository) -> None:
    repo.save("text", "Hello world")
    assert repo.count() == 1


def test_save_returns_id(repo: HistoryRepository) -> None:
    id1 = repo.save("latex", r"\frac{1}{2}")
    id2 = repo.save("text", "plain")
    assert id1 == 1
    assert id2 == 2


def test_list_newest_first(repo: HistoryRepository) -> None:
    repo.save("text", "first")
    repo.save("latex", "second")
    records = repo.list_records()
    assert records[0].result == "second"
    assert records[1].result == "first"


def test_list_pagination(repo: HistoryRepository) -> None:
    for i in range(5):
        repo.save("text", f"item {i}")
    page1 = repo.list_records(limit=2, offset=0)
    page2 = repo.list_records(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0].result != page2[0].result


def test_get_by_id(repo: HistoryRepository) -> None:
    repo.save("markdown", "# Hello", thumbnail=b"\x89PNG", api_model="gpt-4o")
    record = repo.get_by_id(1)
    assert record is not None
    assert record.content_type == "markdown"
    assert record.thumbnail == b"\x89PNG"
    assert record.api_model == "gpt-4o"


def test_get_by_id_missing(repo: HistoryRepository) -> None:
    assert repo.get_by_id(999) is None


def test_search(repo: HistoryRepository) -> None:
    repo.save("text", "The quadratic formula")
    repo.save("latex", r"\frac{a}{b}")
    repo.save("text", "plain text only")

    results = repo.search("quadratic")
    assert len(results) == 1
    assert "quadratic" in results[0].result


def test_search_no_results(repo: HistoryRepository) -> None:
    repo.save("text", "Hello")
    assert repo.search("xyz123notfound") == []


def test_delete_expired(repo: HistoryRepository) -> None:
    import sqlite3
    from datetime import datetime, timedelta, timezone

    # Insert a record with old timestamp directly
    conn = repo._get_conn()
    old_date = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()
    conn.execute(
        "INSERT INTO history (created_at, content_type, result) VALUES (?, ?, ?)",
        (old_date, "text", "old record"),
    )
    conn.commit()

    repo.save("text", "new record")
    assert repo.count() == 2

    deleted = repo.delete_expired(retention_days=7)
    assert deleted == 1
    assert repo.count() == 1
    assert repo.list_records()[0].result == "new record"


def test_delete_expired_keeps_recent(repo: HistoryRepository) -> None:
    repo.save("text", "recent record")
    deleted = repo.delete_expired(retention_days=7)
    assert deleted == 0
    assert repo.count() == 1
