from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from core.clipboard import detect_content_type
from models.enums import ContentType


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Hello world", ContentType.PLAIN_TEXT),
        (r"\frac{1}{2}", ContentType.PURE_LATEX),
        ("The formula $E=mc^2$ is famous.", ContentType.MARKDOWN),
        ("$$\\int_0^1 x dx = \\frac{1}{2}$$", ContentType.MARKDOWN),
        ("# Heading", ContentType.MARKDOWN),
        ("Some **bold** text", ContentType.MARKDOWN),
        (r"\begin{pmatrix} a & b \end{pmatrix}", ContentType.PURE_LATEX),
        ("plain text with no special chars", ContentType.PLAIN_TEXT),
        ("| Variable | Value |\n|----------|-------|\n| x | 3.14 |", ContentType.MARKDOWN),
    ],
)
def test_detect_content_type(text: str, expected: ContentType) -> None:
    assert detect_content_type(text) == expected
