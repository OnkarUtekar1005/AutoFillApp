"""
Scan a root folder for client filing folders.

Preferred layout:
  root/
    ClientName_L01234MH2020PTC123456/
      data/            <- files to extract AOC-4 fields from
        balance_sheet.pdf
        profit_loss.xlsx
        auditors_report.docx
      attachments/      <- files uploaded as-is to MCA, never parsed for fields
        signed_balance_sheet.pdf
        aoc2.pdf

  data/ may contain files directly (single filing period) or date subfolders
  (multiple periods for the same client), e.g. data/2024-25/... , data/2025-03-31/...

Backward-compatible fallback layouts (still scanned, just without CIN/attachments
support — a warning is logged so the user knows to migrate):
  root/ClientName/DateFolder/files    (old client/date/files layout)
  root/ClientName/files               (old client/files layout, no date folder)
  root/files                          (single filing, root itself is the job)
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from extractor.ingestion.client_folder import parse_client_folder_name

logger = logging.getLogger(__name__)

_SUPPORTED_EXTS = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv",
                   ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

_MONTH_NUM = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}

# Patterns to normalise folder names to a canonical date string
_DATE_PARSERS = [
    # ISO: 2025-03-31
    (re.compile(r'^(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])$'), lambda m: f"{m[1]}-{m[2]}-{m[3]}"),
    # Indian: 31-03-2025 or 31/03/2025
    (re.compile(r'^([0-2]\d|3[01])[-\/](0[1-9]|1[0-2])[-\/](20\d{2})$'), lambda m: f"{m[3]}-{m[2]}-{m[1]}"),
    # FY: 2024-25 or 2024-2025
    (re.compile(r'^(20\d{2})[-–](20)?(\d{2})$'), lambda m: f"{m[1]}-{m[3]}"),
    # Year only: 2025
    (re.compile(r'^(20\d{2})$'), lambda m: m[1]),
    # Month-Year: March_2025 / March-2025
    (re.compile(
        r'^(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
        r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)[-_ ]?(20\d{2})$',
        re.IGNORECASE,
    ), lambda m: f"{m[2]}-{_MONTH_NUM.get(m[1][:3].lower(), '??')}"),
]


def _parse_folder_date(name: str) -> str:
    """Try to parse the folder name into a canonical date/period string.
    Returns the parsed string, or the original name if no pattern matches."""
    for pattern, formatter in _DATE_PARSERS:
        m = pattern.match(name.strip())
        if m:
            try:
                return formatter(m.groups())
            except Exception:
                pass
    return name


@dataclass
class FilingFolder:
    client_name: str
    period_label: str              # canonical form of the date/period
    folder_path: Path              # the client's root folder (ClientName_CIN/, or legacy equivalent)
    data_folder: Path              # folder actually scanned for extraction files (may equal folder_path)
    cin: str | None = None
    cin_source: str = "not_found"  # "folder_name" | "document_text" | "not_found"
    attachments_folder: Path | None = None
    files: list[Path] = field(default_factory=list)              # files to extract fields from
    attachment_files: list[Path] = field(default_factory=list)   # files cataloged only, never parsed


def _collect_files(folder: Path) -> list[Path]:
    """Recursively collect all supported files under a folder, skipping our own
    output (a nested finaloutput/ dir) so generated Excels are never re-ingested
    as source documents."""
    files = []
    for item in folder.rglob("*"):
        parts = {p.lower() for p in item.parts}
        if (item.is_file()
                and not item.name.startswith('.')
                and item.suffix.lower() in _SUPPORTED_EXTS
                and item.name != "extracted.json"
                and "finaloutput" not in parts):
            files.append(item)
    return sorted(files)


def _direct_files(folder: Path) -> list[Path]:
    """Collect supported files directly in a folder (non-recursive)."""
    return [
        f for f in sorted(folder.iterdir())
        if f.is_file()
        and not f.name.startswith('.')
        and f.suffix.lower() in _SUPPORTED_EXTS
        and f.name != "extracted.json"
    ]


def _guess_period_from_files(files: list[Path]) -> str:
    """Try to extract FY/period from file names when no date folder exists."""
    fy_re = re.compile(r'(20\d{2})[-_](20)?(\d{2})', re.IGNORECASE)
    for f in files:
        m = fy_re.search(f.name)
        if m:
            return f"{m.group(1)}-{m.group(3)}"
    return "unknown"


def _scan_new_layout(client_dir: Path, data_dir: Path) -> list[FilingFolder]:
    """ClientName_CIN/data/ (+attachments/) layout."""
    client_name, cin = parse_client_folder_name(client_dir.name)
    cin_source = "folder_name" if cin else "not_found"

    attachments_dir = client_dir / "attachments"
    attachment_files = _collect_files(attachments_dir) if attachments_dir.is_dir() else []
    if not cin:
        logger.warning(
            f"No CIN found in folder name '{client_dir.name}' — rename to "
            f"'{client_dir.name}_<21-char-CIN>' so filings can be matched by CIN. "
            f"Falling back to extracting CIN from document text."
        )

    filings: list[FilingFolder] = []
    date_subdirs = [d for d in sorted(data_dir.iterdir()) if d.is_dir() and not d.name.startswith('.')]

    date_filings_found = False
    for date_dir in date_subdirs:
        all_files = _collect_files(date_dir)
        if not all_files:
            continue
        date_filings_found = True
        filings.append(FilingFolder(
            client_name=client_name, cin=cin, cin_source=cin_source,
            period_label=_parse_folder_date(date_dir.name),
            folder_path=client_dir, data_folder=date_dir,
            attachments_folder=attachments_dir if attachments_dir.is_dir() else None,
            files=all_files, attachment_files=attachment_files,
        ))

    if not date_filings_found:
        all_files = _collect_files(data_dir)
        period = _guess_period_from_files(all_files) if all_files else "unknown"
        filings.append(FilingFolder(
            client_name=client_name, cin=cin, cin_source=cin_source,
            period_label=period, folder_path=client_dir, data_folder=data_dir,
            attachments_folder=attachments_dir if attachments_dir.is_dir() else None,
            files=all_files, attachment_files=attachment_files,
        ))

    return filings


def _scan_legacy_client_dir(client_dir: Path) -> list[FilingFolder]:
    """Old client/date/files or client/files layout — no CIN, no attachments split."""
    filings: list[FilingFolder] = []
    client_subdirs = [d for d in sorted(client_dir.iterdir()) if d.is_dir() and not d.name.startswith('.')]

    date_filings_found = False
    for date_dir in client_subdirs:
        all_files = _collect_files(date_dir)
        if not all_files:
            continue
        date_filings_found = True
        filings.append(FilingFolder(
            client_name=client_dir.name, period_label=_parse_folder_date(date_dir.name),
            folder_path=client_dir, data_folder=date_dir, files=all_files,
        ))

    if not date_filings_found:
        all_files = _collect_files(client_dir)
        if all_files:
            filings.append(FilingFolder(
                client_name=client_dir.name, period_label=_guess_period_from_files(all_files),
                folder_path=client_dir, data_folder=client_dir, files=all_files,
            ))

    if filings:
        logger.warning(
            f"'{client_dir.name}' is using the legacy folder layout (no data/ + attachments/ split, "
            f"no CIN in folder name). It still works, but consider migrating to "
            f"'{client_dir.name}_<CIN>/data/' + '.../attachments/' for CIN tracking and attachment checklists."
        )
    return filings


def scan_client_folder(client_path: str | Path, name: str | None = None, cin: str | None = None) -> list[FilingFolder]:
    """
    Build FilingFolder(s) for ONE registered client whose folder lives at an
    arbitrary path (registry mode — not under a shared root). Handles both a
    ClientName_CIN folder with data/ + attachments/, and a plain folder holding
    the documents directly. `name`/`cin` from the registry override whatever the
    folder name implies.
    """
    client_dir = Path(client_path)
    if not client_dir.is_dir():
        return []

    data_dir = client_dir / "data"
    if data_dir.is_dir():
        filings = _scan_new_layout(client_dir, data_dir)
    else:
        files = _collect_files(client_dir)
        filings = [FilingFolder(
            client_name=name or client_dir.name,
            period_label=_guess_period_from_files(files),
            folder_path=client_dir, data_folder=client_dir, files=files,
        )] if files else []

    for f in filings:
        if name:
            f.client_name = name
        if cin:
            f.cin = cin
            f.cin_source = "registry"
    return filings


def scan_root(root_path: str | Path) -> list[FilingFolder]:
    """Scan root_path for client filing folders (new or legacy layout, auto-detected)."""
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Root folder not found: {root}")

    filings: list[FilingFolder] = []
    subdirs = [
        d for d in sorted(root.iterdir())
        if d.is_dir() and not d.name.startswith('.') and d.name.lower() != "finaloutput"
    ]
    root_direct = _direct_files(root)

    # ── Legacy layout C: files directly in root (single filing) ────────────
    if root_direct:
        all_files = _collect_files(root)
        filings.append(FilingFolder(
            client_name=root.name, period_label=_guess_period_from_files(all_files),
            folder_path=root, data_folder=root, files=all_files,
        ))
        return filings

    for client_dir in subdirs:
        data_dir = client_dir / "data"
        if data_dir.is_dir():
            filings.extend(_scan_new_layout(client_dir, data_dir))
        else:
            filings.extend(_scan_legacy_client_dir(client_dir))

    return filings
