"""
Map raw extracted line items to AOC-4 field keys.

Confidence levels:
  HIGH  — exact synonym match
  MED   — partial word-overlap match (score >= 0.65) or prior-year variant
  LOW   — weak partial match (score >= 0.40) or OCR'd text

Prior-year handling:
  If a label starts with "previous year" or "prior year", the prefix is stripped,
  the remainder is matched to a base field, then the _prior_year variant is returned.
"""
import re
from dataclasses import dataclass

from extractor.mapping.schema import SYNONYM_MAP, FIELD_BY_KEY


_PRIOR_YEAR_PREFIXES = (
    "previous year ",
    "prior year ",
    "previous yr ",
    "prior yr ",
    "py ",
    "p.y. ",
)

_SKIP_LABELS = frozenset([
    "total", "net", "less", "add", "sub-total", "subtotal", "grand total",
    "amount", "value", "balance", "particulars", "description", "note",
    "schedule", "figures", "notes", "sr no", "sr.", "no.",
])


@dataclass
class MappedField:
    field_key: str
    raw_label: str
    raw_value: str
    confidence: str       # HIGH | MED | LOW
    page: int | None
    bbox: dict | None
    ocr_confidence: float | None
    source_file: str = ""


def _clean_label(label: str) -> str:
    label = label.lower().strip()
    # Remove unit annotations like "(Rs. in lakhs)" or "(₹ in crores)"
    label = re.sub(r'\(rs\.?\s*in\s*(?:lakhs?|crores?)\)', '', label)
    label = re.sub(r'\(₹\s*in\s*\w+\)', '', label)
    label = re.sub(r'\(in\s*(?:lakhs?|crores?|thousands?)\)', '', label)
    # Remove trailing note references like "(1)" "(Note 5)"
    label = re.sub(r'\(\s*(?:note\s*)?\d+\s*\)', '', label)
    # Remove year annotations like "(2024-25)"
    label = re.sub(r'\(\s*20\d{2}[-–\/]\d{2}\s*\)', '', label)
    label = re.sub(r'\s+', ' ', label).strip()
    label = label.rstrip('.:')
    return label


def _clean_value(raw: str) -> str:
    v = raw.strip()
    v = re.sub(r'[₹$,\s]', '', v)
    # Parentheses = negative number
    if v.startswith('(') and v.endswith(')'):
        v = '-' + v[1:-1]
    return v


def _exact_match(label: str) -> str | None:
    return SYNONYM_MAP.get(_clean_label(label))


def _partial_match(label: str) -> tuple[str | None, float]:
    """
    Word-overlap match against all synonyms.
    Requires at least 2 shared words and score >= 0.40.
    """
    cleaned = _clean_label(label)
    words = set(cleaned.split())
    if len(words) < 2:
        return None, 0.0

    best_key = None
    best_score = 0.0
    for syn, fkey in SYNONYM_MAP.items():
        syn_words = set(syn.split())
        if len(syn_words) < 2:
            continue
        intersection = words & syn_words
        if len(intersection) < 2:
            continue
        score = len(intersection) / max(len(syn_words), len(words))
        if score > best_score:
            best_score = score
            best_key = fkey

    return best_key, best_score


def _strip_prior_year_prefix(label: str) -> tuple[bool, str]:
    """Return (is_prior_year, label_without_prefix)."""
    cl = label.lower().strip()
    for prefix in _PRIOR_YEAR_PREFIXES:
        if cl.startswith(prefix):
            return True, label[len(prefix):].strip()
    return False, label


def map_line_items(
    line_items: list[dict],
    source_file: str = "",
) -> list[MappedField]:
    """Map raw line items to AOC-4 field keys with confidence scores."""
    results: list[MappedField] = []
    seen_keys: set[str] = set()

    for item in line_items:
        label: str = item.get("raw_label", "")
        value: str = item.get("raw_value", "")
        page = item.get("page")
        bbox = item.get("bbox")
        ocr_conf = item.get("ocr_confidence")

        if not value or not value.strip():
            continue

        cleaned_label = _clean_label(label)
        if cleaned_label in _SKIP_LABELS:
            continue

        # ── Detect prior-year prefix ──────────────────────────────────────────
        is_prior_year, base_label = _strip_prior_year_prefix(label)

        # ── Attempt exact match ───────────────────────────────────────────────
        field_key = _exact_match(base_label if is_prior_year else label)
        confidence = "HIGH"

        # ── Attempt partial match if exact failed ─────────────────────────────
        if not field_key:
            field_key, score = _partial_match(base_label if is_prior_year else label)
            if field_key and score >= 0.65:
                confidence = "MED"
            elif field_key and score >= 0.40:
                confidence = "LOW"
            else:
                field_key = None

        # ── Resolve prior-year variant ────────────────────────────────────────
        if field_key and is_prior_year:
            py_key = field_key + "_prior_year"
            if py_key in FIELD_BY_KEY:
                field_key = py_key
                # Prior year extraction is inherently less reliable
                if confidence == "HIGH":
                    confidence = "MED"
            else:
                field_key = None   # No prior-year variant for this field

        if not field_key:
            continue

        # ── Type-safety guard ─────────────────────────────────────────────────
        fdef = FIELD_BY_KEY.get(field_key)
        if fdef and fdef.data_type in ("string", "text", "date", "enum", "boolean"):
            val_stripped = re.sub(r'[,.\s\-₹$()/]', '', value.strip())
            if val_stripped.isdigit():
                # A bare number is never a valid date/enum/boolean (e.g. a '0'
                # cell must not become board_report_date). For string/text only
                # reject long digit runs (short codes/numbers can be legitimate).
                if fdef.data_type in ("date", "enum", "boolean") or len(val_stripped) >= 5:
                    continue

        # ── OCR confidence override ───────────────────────────────────────────
        if ocr_conf is not None:
            if ocr_conf < 0.70:
                confidence = "LOW"
            elif ocr_conf < 0.85 and confidence == "HIGH":
                confidence = "MED"

        # ── Keep first occurrence per key ─────────────────────────────────────
        if field_key in seen_keys:
            continue
        seen_keys.add(field_key)

        cleaned_value = _clean_value(value)
        if not cleaned_value:
            continue

        results.append(MappedField(
            field_key=field_key,
            raw_label=label,
            raw_value=cleaned_value,
            confidence=confidence,
            page=page,
            bbox=bbox,
            ocr_confidence=ocr_conf,
            source_file=source_file,
        ))

    return results
