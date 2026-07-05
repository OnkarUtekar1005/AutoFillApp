"""
OCR extraction using Tesseract (pytesseract) + pdf2image.

For scanned PDFs: convert each page to image, run Tesseract,
parse the OCR text for label-value pairs.
For image files: run Tesseract directly.

Tesseract must be installed and on PATH:
  Windows: https://github.com/UB-Mannheim/tesseract/wiki
  Set TESSDATA_PREFIX if needed.
"""
import io
import re

try:
    import pytesseract
    from PIL import Image
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    _PDF2IMAGE_AVAILABLE = False


def _is_numeric_cell(value: str) -> bool:
    cleaned = re.sub(r'[₹$,\s()\-]', '', str(value))
    try:
        float(cleaned)
        return bool(cleaned)
    except ValueError:
        return False


def _parse_ocr_text(text: str, page_num: int) -> list[dict]:
    """
    Parse a page of OCR'd text for (label, value) pairs.
    Two strategies:
      1. Lines where label and number are separated by 2+ spaces or a tab
      2. Lines where the number is at the far right (common in financial tables)
    """
    items = []
    line_pattern = re.compile(
        r'^(.{4,60}?)\s{2,}([\d,₹$\(\)\-\.]+(?:\.\d{1,2})?)\s*$',
        re.MULTILINE,
    )
    for m in line_pattern.finditer(text):
        label = m.group(1).strip()
        value = m.group(2).strip()
        if _is_numeric_cell(value) and len(label) >= 4:
            items.append({
                "raw_label": label,
                "raw_value": value,
                "page": page_num,
                "bbox": None,
                "ocr_confidence": None,  # per-word confidence requires hOCR; skip for now
            })

    return items


def _ocr_image(img: "Image.Image", page_num: int) -> list[dict]:
    """Run Tesseract on a PIL image and parse the result."""
    # PSM 6: Assume a uniform block of text (good for financial statements)
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(img, config=custom_config, lang='eng')
    items = _parse_ocr_text(text, page_num)
    return items, text


def extract_ocr_pdf(file_bytes: bytes) -> tuple[list[dict], str]:
    """
    Convert each PDF page to an image and run Tesseract.
    Returns (line_items, ingest_path).
    """
    if not _TESSERACT_AVAILABLE:
        raise RuntimeError(
            "pytesseract is not installed. Run: pip install pytesseract\n"
            "Also install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki"
        )
    if not _PDF2IMAGE_AVAILABLE:
        raise RuntimeError(
            "pdf2image is not installed. Run: pip install pdf2image\n"
            "Also install poppler for Windows: https://github.com/oschwartz10612/poppler-windows"
        )

    images = convert_from_bytes(file_bytes, dpi=300)
    all_items: list[dict] = []
    full_text_pages: list[str] = []

    for page_num, img in enumerate(images, start=1):
        items, page_text = _ocr_image(img, page_num)
        all_items.extend(items)
        full_text_pages.append(page_text)

    # Also scan full text for company info, dates, audit opinion
    from extractor.extraction.text_fields import extract_text_fields
    all_items.extend(extract_text_fields("\n".join(full_text_pages)))

    return all_items, "OCR"


def extract_ocr_image(file_bytes: bytes, mime_type: str) -> tuple[list[dict], str]:
    """Run Tesseract on a standalone image file."""
    if not _TESSERACT_AVAILABLE:
        raise RuntimeError("pytesseract is not installed.")

    img = Image.open(io.BytesIO(file_bytes))
    items, text = _ocr_image(img, page_num=1)

    from extractor.extraction.text_fields import extract_text_fields
    items.extend(extract_text_fields(text))

    return items, "OCR"
