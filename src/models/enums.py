from __future__ import annotations

from enum import Enum


class ContentType(str, Enum):
    PLAIN_TEXT = "text"
    PURE_LATEX = "latex"
    MARKDOWN = "markdown"


class AppState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"
    RECOGNIZING = "recognizing"
    PASTING = "pasting"
