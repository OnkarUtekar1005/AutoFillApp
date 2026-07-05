"""
Extract non-numeric AOC-4 fields from document full text:
  - CIN, company name, financial year, balance sheet date
  - DIN, DSC holder name, registered address
  - Audit opinion, auditor name, firm reg no, audit date
  - Board report date, board meetings count
  - Dividend and CSR info
"""
import re

_MONTH_MAP = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12',
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'jun': '06', 'jul': '07', 'aug': '08', 'sep': '09',
    'oct': '10', 'nov': '11', 'dec': '12',
}

_MONTH_NAMES = '|'.join(sorted(_MONTH_MAP.keys(), key=len, reverse=True))

_DATE_PATTERNS = [
    # DD/MM/YYYY  or  DD-MM-YYYY
    re.compile(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](20\d{2})\b'),
    # 20th September 2025 / 20 September 2025
    re.compile(
        rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_NAMES})\.?\s+(20\d{{2}})\b',
        re.IGNORECASE,
    ),
    # September 20, 2025 / September 2025
    re.compile(
        rf'\b({_MONTH_NAMES})\.?\s+(\d{{1,2}}),?\s+(20\d{{2}})\b',
        re.IGNORECASE,
    ),
    # YYYY-MM-DD (ISO)
    re.compile(r'\b(20\d{2})\-(0[1-9]|1[0-2])\-([0-2]\d|3[01])\b'),
]

# CIN: exactly 21 chars — letter, 5 digits, 2 letters, 4 digits, 3 letters, 6 digits
_CIN_RE = re.compile(r'\b([A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b')

# DIN: 8-digit number preceded by "DIN" label
_DIN_RE = re.compile(r'DIN\s*[:\-–]?\s*(\d{8})\b', re.IGNORECASE)

# Financial year like "2024-25" or "2024-2025"
_FY_RE = re.compile(r'\b(20\d{2})[-–\/](20)?(\d{2})\b')

# Auditor firm reg no: FRN XXXXXX or "Firm Reg. No. XXXXXX"
_FRN_RE = re.compile(
    r'(?:FRN|Firm\s+Reg(?:istration)?\.?\s*No\.?)\s*[:\-–]?\s*([0-9]{6}[A-Z]?)',
    re.IGNORECASE,
)

# Board meetings count
_BOARD_MEETINGS_RE = re.compile(
    r'(\d+)\s+(?:board\s+meetings?|meetings?\s+of\s+the\s+board)',
    re.IGNORECASE,
)


def _normalize_date(m: re.Match, pattern_idx: int) -> str | None:
    try:
        if pattern_idx == 0:
            day, month, year = m.group(1), m.group(2), m.group(3)
        elif pattern_idx == 1:
            day = m.group(1)
            month = _MONTH_MAP.get(m.group(2).lower().rstrip('.'))
            year = m.group(3)
            if not month:
                return None
        elif pattern_idx == 2:
            month = _MONTH_MAP.get(m.group(1).lower().rstrip('.'))
            day = m.group(2)
            year = m.group(3)
            if not month:
                return None
        else:  # ISO
            year, month, day = m.group(1), m.group(2), m.group(3)
        return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    except Exception:
        return None


def _first_date_in(text: str, start: int = 0, window: int = 2000) -> str | None:
    snippet = text[start: start + window]
    for pi, pat in enumerate(_DATE_PATTERNS):
        for m in pat.finditer(snippet):
            result = _normalize_date(m, pi)
            if result:
                return result
    return None


def _find_date_near_keyword(text: str, keyword_re: str, window: int = 1500) -> str | None:
    anchor = re.search(keyword_re, text, re.IGNORECASE)
    if not anchor:
        return None
    return _first_date_in(text, anchor.start(), window)


def _item(label: str, value: str, conf: float = 0.85) -> dict:
    return {"raw_label": label, "raw_value": value,
            "page": None, "bbox": None, "ocr_confidence": conf}


def extract_text_fields(full_text: str) -> list[dict]:
    """Return line-item dicts for non-numeric AOC-4 fields found in the document text."""
    items: list[dict] = []

    # ── CIN ──────────────────────────────────────────────────────────────────
    cin_m = _CIN_RE.search(full_text)
    if cin_m:
        items.append(_item("CIN", cin_m.group(1), 0.95))

    # ── Financial Year ────────────────────────────────────────────────────────
    # Priority: look near "year ended" / "for the year" first
    fy_anchor = re.search(
        r'(?:for\s+the\s+(?:year|period)\s+ended?|year\s+ended?)',
        full_text, re.IGNORECASE,
    )
    fy_snippet = full_text[fy_anchor.start(): fy_anchor.start() + 200] if fy_anchor else full_text[:500]
    fy_m = _FY_RE.search(fy_snippet)
    if not fy_m:
        fy_m = _FY_RE.search(full_text[:2000])
    if fy_m:
        year1 = fy_m.group(1)
        part2 = fy_m.group(3)
        fy_str = f"{year1}-{part2}"
        items.append(_item("financial year", fy_str, 0.90))

    # ── Balance Sheet Date (reporting_period_end) ─────────────────────────────
    bs_date = _find_date_near_keyword(
        full_text,
        r'(?:as\s+at|as\s+on|balance\s+sheet\s+(?:as\s+at|date))',
        window=300,
    )
    if bs_date:
        items.append(_item("Balance Sheet Date", bs_date, 0.90))

    # ── DIN ───────────────────────────────────────────────────────────────────
    din_m = _DIN_RE.search(full_text)
    if din_m:
        items.append(_item("DIN", din_m.group(1), 0.90))

    # ── DSC Holder Name (Director name near DIN) ──────────────────────────────
    # Look for an explicit "Name:" label near the DIN, or a person-name pattern
    # (Title-cased words, 2-4 parts) that is NOT a known non-person term
    _NON_PERSON = re.compile(
        r'\b(?:chartered|accountants?|associates?|company|limited|private|llp|'
        r'directors?|report|office|registered|mumbai|delhi|bangalore|chennai|'
        r'hyderabad|kolkata|pune)\b',
        re.IGNORECASE,
    )
    if din_m:
        pre_din = full_text[max(0, din_m.start() - 500): din_m.start()]
        # Prefer explicit "Name:" label
        name_m = re.search(
            r'(?:Name\s*[:\-–]\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
            pre_din,
        )
        if not name_m:
            # Standalone Title Case name on its own line (2-4 words, no org keywords)
            # Search from end of pre_din window (closest to DIN = most likely the signatory)
            candidates = list(re.finditer(
                r'(?:^|\n)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*(?:\n|$)',
                pre_din,
            ))
            for candidate in reversed(candidates):
                if not _NON_PERSON.search(candidate.group(1)):
                    name_m = candidate
                    break
        if name_m:
            items.append(_item("Director Name", name_m.group(1).strip(), 0.75))

    # ── Registered Office Address ─────────────────────────────────────────────
    addr_anchor = re.search(
        r'Registered\s+Office\s*[:\-–]?\s*',
        full_text, re.IGNORECASE,
    )
    if addr_anchor:
        addr_start = addr_anchor.end()
        # Grab up to 400 chars, stop at double-newline or section header
        addr_snippet = full_text[addr_start: addr_start + 400]
        addr_snippet = re.split(r'\n\s*\n|\n[A-Z]{3,}', addr_snippet)[0]
        addr = " ".join(addr_snippet.split()).strip().rstrip(',.')
        if len(addr) > 10:
            items.append(_item("Registered Office", addr, 0.80))

    # ── Company Name ──────────────────────────────────────────────────────────
    # Try explicit label first
    cname_m = re.search(
        r'(?:Name\s+of\s+(?:the\s+)?[Cc]ompany|Company\s+Name)\s*[:\-–]\s*([^\n]{5,80})',
        full_text,
    )
    if cname_m:
        items.append(_item("Name of Company", cname_m.group(1).strip(), 0.90))
    else:
        # First short line (≤80 chars) in first 1500 chars that ends with a
        # company-type suffix — case-insensitive to handle ALL CAPS headers
        cname_implicit = re.search(
            r'^([A-Za-z][A-Za-z0-9\s\.\-&\(\)\']{4,70}'
            r'(?:Private\s+Limited|Pvt\.?\s+Ltd\.?|Limited|LLP))\s*$',
            full_text[:1500], re.MULTILINE | re.IGNORECASE,
        )
        if cname_implicit:
            items.append(_item("Name of Company", cname_implicit.group(1).strip().title(), 0.75))

    # ── Auditor Name ──────────────────────────────────────────────────────────
    auditor_m = re.search(
        r'For\s+([A-Z][A-Za-z0-9\s&\.,]+?'
        r'(?:Associates|Co\.|LLP|Chartered\s+Accountants?|CAs?))\b',
        full_text,
    )
    if auditor_m:
        items.append(_item("Auditor", auditor_m.group(1).strip(), 0.85))

    # ── Auditor Firm Registration Number ─────────────────────────────────────
    frn_m = _FRN_RE.search(full_text)
    if frn_m:
        items.append(_item("Firm Reg No", frn_m.group(1).strip(), 0.90))

    # ── Auditor Membership Number ─────────────────────────────────────────────
    memb_m = re.search(
        r'(?:M(?:embership)?\.?\s*No\.?|ICAI\s+Membership\s+No\.?)\s*[:\-–]?\s*(\d{5,6})',
        full_text, re.IGNORECASE,
    )
    if memb_m:
        items.append(_item("Membership No", memb_m.group(1).strip(), 0.90))

    # ── Audit Report Date ─────────────────────────────────────────────────────
    audit_date = _find_date_near_keyword(
        full_text,
        r'(?:independent\s+auditor|statutory\s+auditor|auditor[s\']?\s+report)',
        window=3000,
    )
    if audit_date:
        items.append(_item("Date of audit report", audit_date, 0.80))

    # ── Audit Opinion Type ────────────────────────────────────────────────────
    audit_anchor = re.search(
        r'(?:independent\s+auditor|statutory\s+auditor|audit\s+report)',
        full_text, re.IGNORECASE,
    )
    audit_section = (
        full_text[audit_anchor.start(): audit_anchor.start() + 4000]
        if audit_anchor else full_text
    )
    if re.search(r'true\s+and\s+fair\s+view', audit_section, re.IGNORECASE):
        opinion = "unqualified"
    elif re.search(r'\bexcept\s+for\b', audit_section, re.IGNORECASE):
        opinion = "qualified"
    elif re.search(r'adverse\s+opinion', audit_section, re.IGNORECASE):
        opinion = "adverse"
    elif re.search(r'disclaim(?:er|s?)\s+(?:of\s+)?opinion', audit_section, re.IGNORECASE):
        opinion = "disclaimer"
    else:
        opinion = None
    if opinion:
        items.append(_item("audit opinion type", opinion, 0.80))

    # ── Board Report Date ─────────────────────────────────────────────────────
    board_date = _find_date_near_keyword(
        full_text,
        r"(?:board\s+of\s+directors|directors?['’]?\s*report|board['’]?\s*report)",
        window=2000,
    )
    if not board_date:
        board_date = _find_date_near_keyword(full_text, r'on\s+behalf\s+of', window=500)
    if board_date:
        items.append(_item("board report date", board_date, 0.80))

    # ── Board Meetings Count ──────────────────────────────────────────────────
    meetings_m = _BOARD_MEETINGS_RE.search(full_text)
    if meetings_m:
        items.append(_item("Number of board meetings", meetings_m.group(1), 0.85))

    # ── Date Board Approved Financial Statements ──────────────────────────────
    board_approval_date = _find_date_near_keyword(
        full_text,
        r'(?:approval\s+of\s+(?:financial\s+statements|accounts)|'
        r'board\s+meeting\s+(?:held\s+on|dated?)|'
        r'approved\s+(?:the\s+)?financial\s+statements)',
        window=300,
    )
    if board_approval_date:
        items.append(_item("Date of board meeting", board_approval_date, 0.80))

    # ── AGM Date ─────────────────────────────────────────────────────────────
    agm_date = _find_date_near_keyword(
        full_text,
        r'(?:annual\s+general\s+meeting|AGM)\s+(?:be\s+held|held|is\s+scheduled|scheduled)',
        window=500,
    )
    if not agm_date:
        agm_date = _find_date_near_keyword(
            full_text,
            r'(?:date\s+of\s+(?:the\s+)?AGM|AGM\s+(?:date|on|held))',
            window=300,
        )
    if agm_date:
        items.append(_item("Date of AGM", agm_date, 0.80))

    # ── EPS (Basic and Diluted) ───────────────────────────────────────────────
    eps_basic_m = re.search(
        r'(?:Basic\s+EPS|Basic\s+earnings\s+per\s+(?:equity\s+)?share)\s*[:\-–]?\s*([\d,\.]+)',
        full_text, re.IGNORECASE,
    )
    if eps_basic_m:
        items.append(_item("Basic EPS", eps_basic_m.group(1).replace(',', ''), 0.85))

    eps_diluted_m = re.search(
        r'(?:Diluted\s+EPS|Diluted\s+earnings\s+per\s+(?:equity\s+)?share)\s*[:\-–]?\s*([\d,\.]+)',
        full_text, re.IGNORECASE,
    )
    if eps_diluted_m:
        items.append(_item("Diluted EPS", eps_diluted_m.group(1).replace(',', ''), 0.85))

    # ── Dividend ─────────────────────────────────────────────────────────────
    if re.search(r'\bdividend\b', full_text, re.IGNORECASE):
        div_m = re.search(
            r'dividend\s+(?:of|@|at\s+the\s+rate\s+of)?\s*(?:Rs\.?|₹)?\s*([\d,\.]+)',
            full_text, re.IGNORECASE,
        )
        if div_m:
            items.append(_item("Dividend declared", "yes", 0.80))
            items.append(_item("Dividend paid", div_m.group(1).replace(',', ''), 0.75))
        elif re.search(r'(?:declared|recommended|proposed)\s+(?:a\s+)?dividend', full_text, re.IGNORECASE):
            items.append(_item("Dividend declared", "yes", 0.75))

    # ── CSR ───────────────────────────────────────────────────────────────────
    csr_anchor = re.search(r'\bCSR\b|Corporate\s+Social\s+Responsibility', full_text, re.IGNORECASE)
    if csr_anchor:
        csr_section = full_text[csr_anchor.start(): csr_anchor.start() + 2000]
        if re.search(r'not\s+applicable|does\s+not\s+apply|not\s+required', csr_section, re.IGNORECASE):
            items.append(_item("CSR", "no", 0.80))
        else:
            items.append(_item("CSR", "yes", 0.75))
            csr_amt_m = re.search(
                r'(?:amount\s+spent|expenditure)\s*[:\-–]?\s*(?:Rs\.?|₹)?\s*([\d,\.]+)',
                csr_section, re.IGNORECASE,
            )
            if csr_amt_m:
                items.append(_item("CSR expenditure", csr_amt_m.group(1).replace(',', ''), 0.75))

    return items
