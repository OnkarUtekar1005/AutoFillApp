"""
Orchestrate the full extraction pipeline for one FilingFolder:
  1. For each file in data/: extract line items via the free regex/heuristic path
  2. Merge line items from all files (earlier files take precedence on conflicts)
  3. Map to AOC-4 fields
  4. Gap-fill remaining missing/low-confidence fields with a single batched Claude
     call (only fires when there's an actual gap, and only if the firm has opted
     in — see extractor/extraction/llm_gapfill.py's client data safeguard)
  5. Validate
  6. Write extracted.json (next to the source files) + finaloutput/<Client>_<CIN>.xlsx
"""
import json
import logging
from pathlib import Path

from extractor.extraction.router import extract_file, get_markdown_text
from extractor.extraction import llm_gapfill
from extractor.ingestion.folder_scanner import FilingFolder
from extractor.mapping.mapper import map_line_items, MappedField
from extractor.mapping.schema import FIELD_BY_KEY
from extractor.validation.validator import validate

logger = logging.getLogger(__name__)


def _merge_mapped(
    existing: dict[str, MappedField],
    new_fields: list[MappedField],
) -> dict[str, MappedField]:
    """
    Merge new_fields into existing. Existing (higher-priority) fields win
    unless the new field has a higher confidence level.
    """
    confidence_rank = {"HIGH": 3, "MED": 2, "LOW": 1, "LLM": 1}
    for f in new_fields:
        if f.field_key not in existing:
            existing[f.field_key] = f
        else:
            old_rank = confidence_rank.get(existing[f.field_key].confidence, 0)
            new_rank = confidence_rank.get(f.confidence, 0)
            if new_rank > old_rank:
                existing[f.field_key] = f
    return existing


def _run_claude_structuring(filing: FilingFolder, all_mapped: dict) -> tuple[dict, bool, list[dict]]:
    """
    Run the Claude structuring step for one filing. Returns
    (claude_values, overwrite, conversion_log):

      - Gap-fill mode (AOC4_ALLOW_CLAUDE=1): Claude fills only the schema keys
        still missing or LOW-confidence after regex. overwrite=False — the crude
        regex values stay untouched.
      - Full mode (AOC4_CLAUDE_FULL=1): Claude reads the markdown and cleanly
        re-extracts EVERY field. overwrite=True — Claude's clean values take
        precedence over the dirty regex output.

    Never raises — any failure (opt-in not set, Claude outage) just returns
    ({}, False, log) so the free regex results stand as-is.
    """
    if not llm_gapfill.available():
        return {}, False, []

    full = llm_gapfill.full_mode()

    # In gap-fill mode, skip entirely if there's nothing to fill.
    if not full:
        needed_keys = [
            key for key in FIELD_BY_KEY
            if key not in all_mapped or all_mapped[key].confidence == "LOW"
        ]
        if not needed_keys:
            return {}, False, []

    conversion_log: list[dict] = []
    markdown_parts: list[str] = []
    for file_path in filing.files:
        text, stage = get_markdown_text(file_path)
        conversion_log.append({"file": file_path.name, "stage": stage, "chars": len(text)})
        if text:
            markdown_parts.append(f"## {file_path.name}\n\n{text}")

    if not markdown_parts:
        return {}, full, conversion_log

    markdown = "\n\n".join(markdown_parts)

    if full:
        # Only ask Claude for AUTO fields — MANUAL/MCA fields aren't in the
        # documents (SRNs, product codes, service-provider info), so asking
        # would waste tokens and risk hallucination. The CS fills those in Excel.
        all_fields = [
            {
                "key": k, "label": fd.label, "data_type": fd.data_type,
                "synonyms": fd.synonyms, "enum_values": fd.enum_values,
            }
            for k, fd in FIELD_BY_KEY.items() if fd.source == "AUTO"
        ]
        return llm_gapfill.structure_all_fields(markdown, all_fields), True, conversion_log

    needed_fields = [
        {"key": k, "label": FIELD_BY_KEY[k].label, "synonyms": FIELD_BY_KEY[k].synonyms}
        for k in needed_keys
    ]
    return llm_gapfill.gapfill_fields(markdown, needed_fields), False, conversion_log


def process_filing(filing: FilingFolder, root_path: str | Path, verbose: bool = False) -> dict:
    """
    Process all files in a FilingFolder. Returns the structured result dict,
    writes extracted.json to the filing's data folder, and writes
    finaloutput/<Client>_<CIN>.xlsx under root_path.
    """
    all_mapped: dict[str, MappedField] = {}
    doc_log: list[dict] = []

    for file_path in filing.files:
        try:
            line_items, ingest_path = extract_file(file_path)
            mapped = map_line_items(line_items, source_file=file_path.name)
            all_mapped = _merge_mapped(all_mapped, mapped)

            doc_log.append({
                "file": file_path.name,
                "ingest_path": ingest_path,
                "line_items_extracted": len(line_items),
                "fields_mapped": len(mapped),
                "status": "ok",
            })
            if verbose:
                logger.info(
                    f"  {file_path.name}: {ingest_path}, "
                    f"{len(line_items)} items -> {len(mapped)} fields"
                )
        except Exception as exc:
            logger.error(f"  ERROR processing {file_path.name}: {exc}")
            doc_log.append({
                "file": file_path.name,
                "ingest_path": "ERROR",
                "error": str(exc),
                "status": "error",
            })

    # ── Claude structuring: gap-fill (fills holes) OR full clean re-extraction ─
    claude_values, overwrite, conversion_log = _run_claude_structuring(filing, all_mapped)
    for key, value in claude_values.items():
        if key not in FIELD_BY_KEY:
            continue  # ignore unknown keys
        if value in (None, ""):
            continue
        # Gap-fill mode: never overwrite a regex value. Full mode: Claude wins.
        if key in all_mapped and not overwrite:
            continue
        all_mapped[key] = MappedField(
            field_key=key, raw_label=FIELD_BY_KEY[key].label, raw_value=str(value),
            confidence="LLM", page=None, bbox=None, ocr_confidence=None,
            source_file="claude_full" if overwrite else "claude_gapfill",
        )
    if conversion_log:
        mode = "full-structure" if overwrite else "gap-fill"
        logger.info(f"  Claude {mode}: {len(claude_values)} fields | stages: {conversion_log}")

    # Build output fields dict
    fields_out: dict[str, dict] = {}
    for key, mf in all_mapped.items():
        fields_out[key] = {
            "value": mf.raw_value,
            "confidence": mf.confidence,
            "source": mf.source_file,
            "raw_label": mf.raw_label,
            **({"page": mf.page} if mf.page is not None else {}),
        }

    # Merge saved MANUAL values for this client — entered once in Excel, reused
    # automatically on every extraction from here on (see manual_values.py).
    from extractor.ingestion.manual_values import get_for
    for key, value in get_for(filing.cin, filing.client_name).items():
        if key in FIELD_BY_KEY and value not in (None, ""):
            fields_out[key] = {
                "value": value, "confidence": "MANUAL",
                "source": "manual_entry", "raw_label": FIELD_BY_KEY[key].label,
            }

    validation = validate(fields_out)

    attachments_out = [
        {"name": f.name, "size_bytes": f.stat().st_size, "extension": f.suffix.lower(),
         "path": str(f.resolve())}   # absolute path so the extension can upload the file
        for f in filing.attachment_files
    ]

    result = {
        "client_name": filing.client_name,
        "cin": filing.cin,
        "cin_source": filing.cin_source,
        "period": filing.period_label,
        "folder": str(filing.folder_path),
        "data_folder": str(filing.data_folder),
        "total_fields_extracted": len(fields_out),
        "fields": fields_out,
        "validation": validation,
        "documents": doc_log,
        "attachments": attachments_out,
        "gapfill_conversion_log": conversion_log,
    }
    result["status"] = compute_filing_status(result)

    from extractor.output.excel_writer import write_client_excel
    finaloutput_dir = Path(root_path) / "finaloutput"
    excel_path = write_client_excel(result, finaloutput_dir)
    result["excel_path"] = str(excel_path)

    # Write extracted.json LAST so the cached copy includes excel_path — this is
    # what load_cached_results() replays on dashboard startup without re-extracting.
    out_path = filing.data_folder / "extracted.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def process_client_entry(entry: dict, output_root: str | Path, verbose: bool = False) -> list[dict]:
    """Run the pipeline for one registered client (from the client registry).
    output_root is where finaloutput/ is written (a single shared location)."""
    from extractor.ingestion.folder_scanner import scan_client_folder

    filings = scan_client_folder(entry.get("path"), entry.get("name"), entry.get("cin"))
    results = []
    for filing in filings:
        results.append(process_filing(filing, output_root, verbose=verbose))
    return results


def apply_manual_and_revalidate(result: dict, cin: str | None, name: str | None) -> dict:
    """Merge the saved MANUAL values for a client into an already-extracted
    result, then re-validate and recompute status — without re-running
    extraction. Powers filling manual fields directly in the dashboard."""
    from extractor.ingestion.manual_values import get_for

    fields = dict(result.get("fields", {}))
    for key, value in get_for(cin, name).items():
        if key in FIELD_BY_KEY and value not in (None, ""):
            fields[key] = {
                "value": value, "confidence": "MANUAL",
                "source": "manual_entry", "raw_label": FIELD_BY_KEY[key].label,
            }
    result["fields"] = fields
    result["total_fields_extracted"] = len(fields)
    result["validation"] = validate(fields)
    result["status"] = compute_filing_status(result)
    return result


def load_cached_client(entry: dict) -> list[dict]:
    """Replay cached extracted.json for one registered client without re-extracting."""
    from extractor.ingestion.folder_scanner import scan_client_folder

    filings = scan_client_folder(entry.get("path"), entry.get("name"), entry.get("cin"))
    results = []
    for filing in filings:
        cached = filing.data_folder / "extracted.json"
        if cached.exists():
            try:
                results.append(json.loads(cached.read_text(encoding="utf-8")))
            except Exception:
                pass
    return results


def load_cached_results(root_path: str | Path) -> list[dict]:
    """Replay the last extraction from each filing's extracted.json without
    re-running the pipeline. Powers the dashboard landing page: on startup the
    UI shows the previously-extracted portfolio instantly. Filings never yet
    extracted (no extracted.json) are skipped."""
    from extractor.ingestion.folder_scanner import scan_root

    try:
        filings = scan_root(root_path)
    except Exception:
        return []

    results = []
    for filing in filings:
        cached = filing.data_folder / "extracted.json"
        if cached.exists():
            try:
                results.append(json.loads(cached.read_text(encoding="utf-8")))
            except Exception:
                pass
    return results


def compute_filing_status(result: dict) -> str:
    """'Ready' / 'Needs Attention' / 'Missing Attachments' for dashboard status chips.

    Only AUTO-source mandatory gaps block the status — MANUAL mandatory fields
    (AGM held, etc.) are expected to be filled by the CS in Excel afterward, so
    they don't force 'Needs Attention' on a freshly-extracted filing."""
    from extractor.mapping.schema import FIELD_BY_KEY

    v = result["validation"]
    auto_missing = [
        k for k in v.get("missing_mandatory", [])
        if (FIELD_BY_KEY.get(k) and FIELD_BY_KEY[k].source == "AUTO")
    ]
    has_issues = (
        bool(auto_missing)
        or bool(v.get("type_errors"))
        or (v.get("balance_check") and v["balance_check"] != "PASS")
        or (v.get("pnl_check") and v["pnl_check"] != "PASS")
    )
    if has_issues:
        return "Needs Attention"
    if not result.get("attachments"):
        return "Missing Attachments"
    return "Ready"


def revalidate_from_excel(xlsx_path: str | Path) -> dict:
    """Re-read a (possibly user-edited) finaloutput Excel and re-run validation,
    without re-running extraction. Also PERSISTS any MANUAL values the CS typed
    (from both the Fields sheet and the Manual Entry sheet) keyed by CIN, so
    they auto-fill on every future extraction. Attachment status is unaffected
    by an Excel edit, so status only reflects field/validation issues here."""
    from extractor.output.excel_writer import read_fields_from_excel, read_manual_values_from_excel
    from extractor.ingestion.manual_values import set_for, get_for

    path = Path(xlsx_path)
    fields = read_fields_from_excel(path)

    # Collect manual values: the dedicated Manual Entry sheet + any MANUAL-source
    # field the CS filled directly in the Fields sheet.
    manual = read_manual_values_from_excel(path)
    for key, info in fields.items():
        fdef = FIELD_BY_KEY.get(key)
        if fdef and fdef.source == "MANUAL" and info.get("value") not in (None, ""):
            manual[key] = info["value"]

    cin = (fields.get("cin") or {}).get("value")
    name = (fields.get("company_name") or {}).get("value")
    if manual:
        set_for(cin, name, manual)

    # Fold the persisted manual set back in so validation sees them.
    for key, value in get_for(cin, name).items():
        if key in FIELD_BY_KEY and value not in (None, "") and key not in fields:
            fields[key] = {"value": value, "confidence": "MANUAL", "source": "manual_entry"}

    validation = validate(fields)
    has_issues = (
        bool(validation.get("missing_mandatory"))
        or bool(validation.get("type_errors"))
        or (validation.get("balance_check") and validation["balance_check"] != "PASS")
        or (validation.get("pnl_check") and validation["pnl_check"] != "PASS")
    )
    return {
        "fields": fields,
        "validation": validation,
        "status": "Needs Attention" if has_issues else "Fields OK",
    }


def run_all(root_path: str | Path, verbose: bool = True) -> list[dict]:
    """Process every filing folder under root_path."""
    from extractor.ingestion.folder_scanner import scan_root

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    filings = scan_root(root_path)
    if not filings:
        logger.warning(f"No filing folders found under {root_path}")
        return []

    results = []
    for filing in filings:
        logger.info(f"Processing: {filing.client_name} / {filing.period_label} ({len(filing.files)} files)")
        result = process_filing(filing, root_path, verbose=verbose)
        n_fields = result["total_fields_extracted"]
        missing = len(result["validation"]["missing_mandatory"])
        low = len(result["validation"]["low_confidence"])
        logger.info(
            f"  > {n_fields} fields | {missing} mandatory missing | {low} low-confidence | status={result['status']}"
        )
        results.append(result)

    return results
