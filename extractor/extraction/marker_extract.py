"""
Fallback document -> markdown conversion using datalab-to/marker.

Only invoked when markitdown's output for a file was near-empty (i.e. the file
is a scanned/image-only PDF markitdown can't read). marker runs fully local
(no API cost) and has built-in OCR (Surya) plus strong table-structure fidelity,
which is why it's the fallback rather than the primary converter — it's a much
heavier install (PyTorch + ML models) and GPL-licensed, so we only pay that
cost on the files that actually need it.

Optional dependency: `pip install marker-pdf`. If not installed, convert()
returns '' and the caller moves on to the next fallback (Claude).
"""
from pathlib import Path

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    _MARKER_AVAILABLE = True
except ImportError:
    _MARKER_AVAILABLE = False

_converter = None


def available() -> bool:
    return _MARKER_AVAILABLE


def _get_converter():
    global _converter
    if _converter is None:
        _converter = PdfConverter(artifact_dict=create_model_dict())
    return _converter


def convert(file_path: Path) -> str:
    """Convert a (likely scanned) PDF to markdown using marker's local OCR pipeline."""
    if not _MARKER_AVAILABLE:
        return ""
    try:
        rendered = _get_converter()(str(file_path))
        text, _, _ = text_from_rendered(rendered)
        return (text or "").strip()
    except Exception:
        return ""
