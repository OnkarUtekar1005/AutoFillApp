"""
Primary document -> markdown conversion, used only as input to the LLM gap-fill
step (extractor/extraction/llm_gapfill.py) — NOT a replacement for the regex/
heuristic extractors, which still run independently for line-item extraction.

Uses Microsoft's markitdown (MIT license, pure-Python, no GPU/API required).
Its default PDF path is plain text extraction with no OCR, so it works well for
digital PDFs/Excel/Word/CSV but produces near-empty output for scanned pages —
callers should fall back to extractor/extraction/marker_extract.py in that case.
"""
from pathlib import Path

try:
    from markitdown import MarkItDown
    _MARKITDOWN_AVAILABLE = True
except ImportError:
    _MARKITDOWN_AVAILABLE = False

NEAR_EMPTY_THRESHOLD = 200  # chars; below this, assume the page is scanned/unreadable

_converter = None


def available() -> bool:
    return _MARKITDOWN_AVAILABLE


def _get_converter():
    global _converter
    if _converter is None:
        _converter = MarkItDown()
    return _converter


def convert(file_path: Path) -> str:
    """Convert a file to markdown text. Returns '' if markitdown is unavailable or conversion fails."""
    if not _MARKITDOWN_AVAILABLE:
        return ""
    try:
        result = _get_converter().convert(str(file_path))
        return (result.text_content or "").strip()
    except Exception:
        return ""


def is_near_empty(text: str) -> bool:
    return len(text.strip()) < NEAR_EMPTY_THRESHOLD
