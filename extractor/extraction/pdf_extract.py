"""
Extract line items from digital (text-layer) PDFs using pdfplumber.

Handles:
  - Tables with explicit lines (most formatted financial statements)
  - Tables detected by whitespace strategy (some PDFs lack borders)
  - Raw text lines when no tables are found
  - Both current-year AND prior-year columns
"""
import io
import re

import pdfplumber


def _is_numeric_cell(value: str) -> bool:
    cleaned = re.sub(r'[₹$,\s()\-]', '', str(value))
    try:
        float(cleaned)
        return bool(cleaned)
    except ValueError:
        return False


def _is_short_generic(label: str) -> bool:
    s = label.strip()
    if len(s) <= 2:
        return True
    if re.fullmatch(r'[IVXivx]+\.?', s):
        return True
    if re.fullmatch(r'\([a-zA-Z]\)', s):
        return True
    return False


def _is_year_header(cell: str) -> bool:
    """True if cell looks like a financial year header e.g. '2024-25' or '31-03-2025'."""
    s = cell.strip()
    return bool(
        re.fullmatch(r'20\d{2}[-–\/](?:20)?\d{2}', s)
        or re.fullmatch(r'\d{1,2}[-\/]\d{1,2}[-\/]20\d{2}', s)
        or re.fullmatch(r'20\d{2}', s)
    )


def _detect_value_cols(table: list[list], label_col: int) -> tuple[int | None, int | None]:
    """
    Detect which columns hold CY and PY values.
    If a header row exists with year-like content, use those columns.
    Otherwise fall back to: CY = first numeric col right of label, PY = second.
    """
    cy_col: int | None = None
    py_col: int | None = None

    # Check first few rows for a year header
    for row in table[:5]:
        cells = [str(c).strip() if c else "" for c in row]
        year_cols = [ci for ci, c in enumerate(cells) if _is_year_header(c) and ci > label_col]
        if len(year_cols) >= 2:
            return year_cols[0], year_cols[1]
        if len(year_cols) == 1:
            cy_col = year_cols[0]
            # PY might be next numeric col
            break

    # Fallback: scan a few data rows to find numeric columns
    for row in table[1:6]:
        cells = [str(c).strip() if c else "" for c in row]
        num_cols = [ci for ci, c in enumerate(cells) if ci > label_col and _is_numeric_cell(c)]
        if len(num_cols) >= 2:
            return num_cols[0], num_cols[1]
        if len(num_cols) == 1 and cy_col is None:
            cy_col = num_cols[0]

    return cy_col, py_col


def _parse_table(table: list[list], page_num: int) -> list[dict]:
    if not table:
        return []

    items = []

    # Detect label column
    col_text_counts: dict[int, int] = {}
    for row in table:
        for ci, cell in enumerate(row):
            s = str(cell).strip() if cell else ""
            if s and not _is_numeric_cell(s) and len(s) > 3:
                col_text_counts[ci] = col_text_counts.get(ci, 0) + 1

    if not col_text_counts:
        return []

    label_col = max(col_text_counts, key=col_text_counts.get)
    cy_col, py_col = _detect_value_cols(table, label_col)

    for row in table:
        if not row or label_col >= len(row):
            continue
        cells = [str(c).strip() if c else "" for c in row]
        label = cells[label_col]

        if not label or _is_numeric_cell(label) or _is_short_generic(label):
            continue

        # Current year value
        cy_val = ""
        if cy_col is not None and cy_col < len(cells):
            cy_val = cells[cy_col] if _is_numeric_cell(cells[cy_col]) else ""
        if not cy_val:
            # Fallback: first numeric cell to the right
            for ci in range(label_col + 1, min(label_col + 6, len(cells))):
                if _is_numeric_cell(cells[ci]):
                    cy_val = cells[ci]
                    if cy_col is None:
                        cy_col = ci
                    break

        # Prior year value
        py_val = ""
        if py_col is not None and py_col < len(cells):
            py_val = cells[py_col] if _is_numeric_cell(cells[py_col]) else ""
        if not py_val and cy_col is not None:
            # Try the column immediately after cy_col
            next_col = cy_col + 1
            for ci in range(next_col, min(next_col + 3, len(cells))):
                if ci < len(cells) and _is_numeric_cell(cells[ci]):
                    py_val = cells[ci]
                    break

        if cy_val:
            items.append({
                "raw_label": label,
                "raw_value": cy_val,
                "page": page_num,
                "bbox": None,
                "ocr_confidence": None,
            })
        if py_val:
            items.append({
                "raw_label": "previous year " + label,
                "raw_value": py_val,
                "page": page_num,
                "bbox": None,
                "ocr_confidence": None,
            })

    return items


def _parse_text_lines(text: str, page_num: int) -> list[dict]:
    """Heuristic: lines with a label and trailing number (no table structure)."""
    items = []
    pattern = re.compile(
        r'^(.{4,60}?)\s{2,}([\d,₹$\(\)\-\.]+)\s*$', re.MULTILINE
    )
    for m in pattern.finditer(text):
        label, value = m.group(1).strip(), m.group(2).strip()
        if _is_numeric_cell(value) and not _is_short_generic(label):
            items.append({
                "raw_label": label,
                "raw_value": value,
                "page": page_num,
                "bbox": None,
                "ocr_confidence": None,
            })
    return items


def extract_pdf(file_bytes: bytes) -> list[dict]:
    """Extract line items from a digital PDF (text layer present)."""
    from extractor.extraction.text_fields import extract_text_fields

    items: list[dict] = []
    full_text_pages: list[str] = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            full_text_pages.append(page_text)

            # Try lines-based table extraction first (most financial PDFs)
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            })

            if not tables:
                # Fall back to text strategy (PDFs without explicit borders)
                tables = page.extract_tables({
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 5,
                })

            if tables:
                for table in tables:
                    items.extend(_parse_table(table, page_num))
            else:
                items.extend(_parse_text_lines(page_text, page_num))

    # Scan full text for non-numeric fields
    items.extend(extract_text_fields("\n".join(full_text_pages)))
    return items
