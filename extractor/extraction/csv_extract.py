"""Extract line items from CSV financial statements."""
import csv
import io
import re


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


def extract_csv(file_bytes: bytes) -> list[dict]:
    """
    Extract label-value pairs from a CSV financial statement.
    Handles BOM, multiple encodings, and common delimiters.
    Captures both current-year and prior-year columns.
    """
    items: list[dict] = []
    text: str | None = None

    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        return items

    # Detect delimiter
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel

    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        return items

    # Detect label column
    col_text_scores: dict[int, int] = {}
    for row in rows:
        for ci, cell in enumerate(row):
            s = cell.strip()
            if s and not _is_numeric_cell(s) and len(s) > 3:
                col_text_scores[ci] = col_text_scores.get(ci, 0) + 1

    if not col_text_scores:
        return items

    label_col = max(col_text_scores, key=col_text_scores.get)

    # Detect CY / PY columns from a header row
    cy_col: int | None = None
    py_col: int | None = None
    for row in rows[:5]:
        year_cols = [
            ci for ci, c in enumerate(row)
            if ci > label_col and re.search(r'20\d{2}', c.strip())
        ]
        if len(year_cols) >= 2:
            cy_col, py_col = year_cols[0], year_cols[1]
            break
        if len(year_cols) == 1:
            cy_col = year_cols[0]
            break

    for row in rows:
        if not row or label_col >= len(row):
            continue
        label = row[label_col].strip()
        if not label or _is_numeric_cell(label) or _is_short_generic(label):
            continue

        cy_val = ""
        if cy_col is not None and cy_col < len(row) and _is_numeric_cell(row[cy_col]):
            cy_val = row[cy_col].strip()
        if not cy_val:
            for ci in range(label_col + 1, min(label_col + 7, len(row))):
                if _is_numeric_cell(row[ci]):
                    cy_val = row[ci].strip()
                    if cy_col is None:
                        cy_col = ci
                    break

        py_val = ""
        if py_col is not None and py_col < len(row) and _is_numeric_cell(row[py_col]):
            py_val = row[py_col].strip()
        if not py_val and cy_col is not None:
            for ci in range(cy_col + 1, min(cy_col + 4, len(row))):
                if ci < len(row) and _is_numeric_cell(row[ci]):
                    py_val = row[ci].strip()
                    break

        if cy_val:
            items.append({"raw_label": label, "raw_value": cy_val,
                           "page": None, "bbox": None, "ocr_confidence": None})
        if py_val:
            items.append({"raw_label": "previous year " + label, "raw_value": py_val,
                           "page": None, "bbox": None, "ocr_confidence": None})

    # Scan full text for non-numeric fields
    from extractor.extraction.text_fields import extract_text_fields
    full_text = "\n".join(",".join(r) for r in rows)
    items.extend(extract_text_fields(full_text))

    return items
