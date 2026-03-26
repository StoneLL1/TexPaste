from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HistoryRecord:
    id: int
    created_at: str  # ISO8601
    content_type: str
    result: str
    thumbnail: bytes | None = field(default=None)
    api_model: str | None = field(default=None)
