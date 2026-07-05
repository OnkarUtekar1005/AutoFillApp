"""
Route a document to the correct extractor.

Two independent paths through the same file:
  1. extract_file() — the free regex/heuristic line-item extractors
     (pdf/excel/word/csv/OCR), unchanged from before.
  2. get_markdown_text() — markitdown -> marker -> Claude fallback chain,
     used only to feed the LLM gap-fill step in the pipeline for whatever
     fields the free path above left missing.
"""
import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)


def mime_for_file(file_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(file_path))
    ext = file_path.suffix.lower()
    overrides = {
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }
    return overrides.get(ext, mime or "application/octet-stream")


def extract_file(file_path: Path) -> tuple[list[dict], str]:
    """
    Extract line items from any supported file via the free regex/heuristic path.
    Returns (line_items, ingest_path) where ingest_path is one of:
      'PDF_STRUCTURED', 'PDF_OCR', 'PDF_STRUCTURED_FALLBACK', 'EXCEL', 'WORD', 'CSV', 'IMAGE_OCR'
    """
    from extractor.extraction.probe import needs_ocr
    from extractor.extraction.pdf_extract import extract_pdf
    from extractor.extraction.excel_extract import extract_excel
    from extractor.extraction.word_extract import extract_word
    from extractor.extraction.csv_extract import extract_csv
    from extractor.extraction.ocr_extract import extract_ocr_pdf, extract_ocr_image

    file_bytes = file_path.read_bytes()
    mime = mime_for_file(file_path)

    if mime == "application/pdf":
        if needs_ocr(file_bytes):
            try:
                items, path = extract_ocr_pdf(file_bytes)
                return items, "PDF_OCR"
            except Exception:
                # Tesseract/Poppler not installed — fall back to digital extraction
                return extract_pdf(file_bytes), "PDF_STRUCTURED_FALLBACK"
        else:
            return extract_pdf(file_bytes), "PDF_STRUCTURED"

    if mime in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ):
        return extract_excel(file_bytes), "EXCEL"

    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return extract_word(file_bytes), "WORD"

    if mime in ("text/csv", "text/plain") or file_path.suffix.lower() == ".csv":
        return extract_csv(file_bytes), "CSV"

    if mime.startswith("image/"):
        items, path = extract_ocr_image(file_bytes, mime)
        return items, "IMAGE_OCR"

    return [], "UNSUPPORTED"


def get_markdown_text(file_path: Path) -> tuple[str, str]:
    """
    Convert a file to markdown text for the LLM gap-fill step, using the
    cheapest option that works: markitdown (free/local) -> marker (free/local,
    OCR) -> Claude (paid, last resort). Returns (markdown_text, stage_used).
    """
    from extractor.extraction import markitdown_extract

    text = markitdown_extract.convert(file_path)
    if text and not markitdown_extract.is_near_empty(text):
        return text, "MARKITDOWN"

    from extractor.extraction import marker_extract
    marker_text = marker_extract.convert(file_path)
    if marker_text and not markitdown_extract.is_near_empty(marker_text):
        return marker_text, "MARKER_FALLBACK"

    from extractor.extraction import llm_gapfill
    claude_text = llm_gapfill.convert_via_claude(file_path)
    if claude_text:
        return claude_text, "CLAUDE_CONVERT_FALLBACK"

    return (text or marker_text or ""), "UNSUPPORTED"
