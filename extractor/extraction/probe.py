"""Detect whether a PDF has a usable text layer or needs OCR."""
import io

import pdfplumber


def needs_ocr(file_bytes: bytes, threshold: int = 100, probe_pages: int = 3) -> bool:
    """
    Return True if the PDF needs OCR.
    A page is flagged when its text layer has fewer than `threshold` characters —
    which happens with scanned PDFs or image-only pages.
    We probe up to `probe_pages` pages and flag if ANY is below threshold.
    """
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages[:probe_pages]:
                text = page.extract_text() or ""
                if len(text.strip()) < threshold:
                    return True
        return False
    except Exception:
        return True
