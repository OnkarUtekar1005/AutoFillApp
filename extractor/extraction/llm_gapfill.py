"""
The only module that talks to Claude. Uses the Claude Code CLI (`claude -p`)
rather than the Anthropic API, so it runs on whatever account Claude Code is
already authenticated with — a claude.ai Max/Pro subscription's included
usage, not separate pay-per-token API billing.

Kept deliberately narrow to minimize usage, per project direction: markitdown
is the primary converter, marker is a free local fallback, and Claude is used
last and only for the residual gap that neither could fill.

Three entry points:
  1. convert_via_claude(file_path) — last-resort document->text conversion,
     only called when BOTH markitdown and marker produced near-empty text for
     a file (genuinely unreadable any other way, e.g. a low-quality scan).
  2. gapfill_fields(markdown, needed_fields) — called AT MOST ONCE per filing,
     only for schema fields still missing/LOW-confidence after the free regex
     pipeline ran. Fills gaps without touching the regex output.
  3. structure_all_fields(markdown, all_fields) — Claude reads the markdown and
     extracts+CLEANS every field in one pass (correct number/date formatting,
     trimmed spacing, normalized enums). This is the "smart primary structurer":
     when full mode is on, its clean values take precedence over the crude regex
     output. Use when data quality matters more than minimizing Claude usage.

All three return {} / "" (never raise) so a Claude outage or missing opt-in
never blocks the free extraction path.

Requires the `claude` CLI to be installed and logged in (same as this
session). No API key, no `anthropic` pip package.

CLIENT DATA SAFEGUARD
----------------------
This is the only place in the codebase where client financial documents (CIN,
DIN, balance sheets, P&L, director names, etc.) can leave the machine. Several
separate switches gate how much:

  1. AOC4_ALLOW_CLAUDE=1 — must be set explicitly (OFF by default) before
     ANY Claude usage happens: gapfill_fields() and structure_all_fields()
     (text only, no file access, no permission bypass) are gated on this.
  2. AOC4_CLAUDE_FULL=1 — selects full clean structuring (structure_all_fields)
     over gap-fill-only. Requires #1 as well. This sends the full document
     markdown to Claude on every filing (more usage), in exchange for clean,
     correctly-formatted data across all fields rather than dirty regex output.
  3. AOC4_ALLOW_CLAUDE_FILE_READ=1 — a second, stricter opt-in required in
     ADDITION to #1 before convert_via_claude() (the raw-file fallback) runs.
     This path needs Claude's Read tool with permission prompts bypassed
     (`--permission-mode bypassPermissions`, scoped to `--tools Read` only)
     so it can run unattended in a batch script — Read normally requires an
     interactive approval Claude Code would otherwise wait on forever in a
     headless run. Off by default since it's a stronger trust decision than #1.

Per Anthropic's terms, data submitted through Claude Code / the API is NOT
used to train Anthropic's models by default — see https://privacy.anthropic.com.
Everything else in this pipeline (the regex extractors, markitdown, marker)
runs 100% locally and never transmits data anywhere.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

_CLAUDE_MODEL = "sonnet"
_claude_path_cache: str | None = None
_claude_path_resolved = False


def _resolve_claude() -> str | None:
    global _claude_path_cache, _claude_path_resolved
    if not _claude_path_resolved:
        _claude_path_cache = shutil.which("claude")
        _claude_path_resolved = True
    return _claude_path_cache


def available() -> bool:
    """Base switch for text-only Claude usage (gapfill_fields). See the
    client data safeguard note in this module's docstring."""
    return bool(_resolve_claude()) and os.environ.get("AOC4_ALLOW_CLAUDE") == "1"


def full_mode() -> bool:
    """True when Claude should do full clean structuring of every field
    (structure_all_fields) rather than only filling gaps. Requires the base
    opt-in too. See the client data safeguard note in this module's docstring."""
    return available() and os.environ.get("AOC4_CLAUDE_FULL") == "1"


def _file_read_available() -> bool:
    """Stricter, additional switch required for convert_via_claude()."""
    return available() and os.environ.get("AOC4_ALLOW_CLAUDE_FILE_READ") == "1"


def claude_status() -> dict:
    """A snapshot of whether Claude data-cleaning is active, for the UI badge.
    `mode` is what an extraction would actually do right now:
      - "full"    : Claude re-extracts + cleans every AUTO field (best data)
      - "gapfill" : Claude only fills missing/LOW fields, regex output kept
      - "off"     : no Claude — raw regex only (dirty values, manual fixing)
    """
    cli = _resolve_claude()
    allow = os.environ.get("AOC4_ALLOW_CLAUDE") == "1"
    full = os.environ.get("AOC4_CLAUDE_FULL") == "1"
    if cli and allow and full:
        mode = "full"
    elif cli and allow:
        mode = "gapfill"
    else:
        mode = "off"
    return {
        "enabled": bool(cli) and allow,
        "mode": mode,
        "cli_found": bool(cli),
        "cli_path": cli,
        "allow_flag": allow,
        "full_flag": full,
    }


def _unwrap_artifact(obj: dict) -> dict:
    """
    The CLI's structured-output occasionally wraps the real object under a single
    template-placeholder key, e.g. {"$FUNCTION_NAME": "{\\"cin\\": \\"...\\"}"}
    or {"$1": {...}} — the actual field map is intact, just nested (and often
    stringified) one level down. Recover it. Returns obj unchanged if it isn't
    this artifact shape.
    """
    if len(obj) == 1:
        (k, v), = obj.items()
        if isinstance(k, str) and k.startswith("$"):
            if isinstance(v, dict):
                return v
            if isinstance(v, str):
                try:
                    inner = json.loads(v)
                    if isinstance(inner, dict):
                        return inner
                except Exception:
                    pass
    return obj


def _json_result(data: dict | None) -> dict:
    """Pull the field map out of a claude-CLI JSON response. Prefers the
    already-validated `structured_output` object (present when --json-schema is
    used); falls back to parsing the free-text `result`. Unwraps the occasional
    template-placeholder artifact (see _unwrap_artifact). Returns {} on miss."""
    if not data:
        return {}
    candidate = data.get("structured_output")
    if not isinstance(candidate, dict):
        try:
            candidate = json.loads(data.get("result") or "{}")
        except Exception:
            return {}
    if not isinstance(candidate, dict):
        return {}
    return _unwrap_artifact(candidate)


def _run_claude(args: list[str], timeout: int, prompt: str | None = None) -> dict | None:
    """
    Invoke the claude CLI with a resolved absolute path and an argv list
    (never a shell string) so document content can never be interpreted as
    shell syntax, even though the CLI itself is a .cmd shim on Windows.

    The prompt is always piped via stdin, never passed as a CLI argument:
    on Windows, a .cmd shim is executed through cmd.exe's line-oriented batch
    parser, which truncates any argv element at the first embedded newline —
    silently corrupting any multi-line prompt (i.e. any real document text)
    passed as an argument. stdin has no such limitation.
    """
    claude_path = _resolve_claude()
    if not claude_path:
        return None
    try:
        # encoding="utf-8" is REQUIRED, not cosmetic: without it, subprocess uses
        # the OS locale codec (cp1252 on Windows), which cannot encode ₹, →,
        # em-dashes, or any non-Latin1 char — and real financial documents are
        # full of ₹. errors="replace" keeps a stray undecodable byte in Claude's
        # output from crashing the read.
        proc = subprocess.run(
            [claude_path, *args],
            input=prompt, capture_output=True, text=True, timeout=timeout,
            shell=False, encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout)
        if data.get("is_error"):
            return None
        return data
    except Exception:
        return None


def convert_via_claude(file_path: Path) -> str:
    """Send a single unreadable file to Claude (via its own Read tool) and
    ask it to transcribe it to markdown. Requires AOC4_ALLOW_CLAUDE_FILE_READ=1
    in addition to the base opt-in — see the client data safeguard note above."""
    if not _file_read_available():
        return ""
    prompt = (
        f"Read the file at {file_path} and transcribe its content to markdown, "
        "preserving all table structure and figures exactly as shown. "
        "Output only the markdown."
    )
    data = _run_claude([
        "-p",
        "--output-format", "json",
        "--tools", "Read",
        "--add-dir", str(file_path.parent),
        "--permission-mode", "bypassPermissions",
        "--model", _CLAUDE_MODEL,
    ], timeout=180, prompt=prompt)
    if not data:
        return ""
    return (data.get("result") or "").strip()


def gapfill_fields(markdown_text: str, needed_fields: list[dict]) -> dict:
    """
    Ask Claude to fill specific AOC-4 field keys from already-converted markdown text.

    needed_fields: [{"key": ..., "label": ..., "synonyms": [...]}, ...]
    Returns {field_key: value_string} for whatever Claude could confidently find.
    Returns {} on any failure, missing opt-in, or empty input — callers merge
    results in at confidence tier "LLM" and must never let this raise into the
    pipeline (a Claude outage should never block the free regex extraction).
    No file access, no permission bypass needed — gated on AOC4_ALLOW_CLAUDE alone.
    """
    if not available() or not markdown_text.strip() or not needed_fields:
        return {}

    field_list = "\n".join(
        f"- {f['key']}: {f['label']} (also known as: {', '.join(f['synonyms'][:5])})"
        for f in needed_fields
    )
    prompt = (
        "You are extracting specific fields from an Indian company's financial statements "
        "for an AOC-4 MCA filing. Below is the document content, converted to markdown, "
        "followed by a list of fields still missing. Return a JSON object mapping field key "
        "to the value found (numbers as plain strings, no commas), for fields you can "
        "confidently find. Omit any field you cannot find with confidence — do not guess.\n\n"
        f"Fields needed:\n{field_list}\n\n"
        f"Document content:\n{markdown_text[:100000]}"
    )
    data = _run_claude([
        "-p",
        "--output-format", "json",
        "--tools", "",
        "--json-schema", '{"type":"object","additionalProperties":{"type":"string"}}',
        "--model", _CLAUDE_MODEL,
    ], timeout=120, prompt=prompt)
    return _json_result(data)


_TYPE_RULES = {
    "numeric": "plain number, digits only — no commas, currency symbols, or units; "
               "a value in parentheses or with a trailing 'Cr'/'Dr' that means negative → prefix with '-'",
    "date": "ISO format YYYY-MM-DD",
    "string": "trimmed, correctly spaced, proper capitalization",
    "text": "trimmed, correctly spaced; collapse runaway whitespace to single spaces",
    "enum": "exactly one of the allowed values",
    "boolean": "'yes' or 'no'",
}


def structure_all_fields(markdown_text: str, all_fields: list[dict]) -> dict:
    """
    Have Claude read the document markdown and extract AND CLEAN every AOC-4
    field in a single pass. This is the smart-structurer path: Claude is told
    to fix formatting the crude regex extractor gets wrong (stray spaces,
    comma-grouped numbers, mixed date formats, mis-split table cells).

    all_fields: [{"key","label","data_type","synonyms","enum_values"?}, ...]
    Returns {field_key: cleaned_value_string}. Only keys Claude is confident
    about are returned. Returns {} on any failure — callers must never let this
    raise into the pipeline.
    """
    if not available() or not markdown_text.strip() or not all_fields:
        return {}

    lines = []
    for f in all_fields:
        rule = _TYPE_RULES.get(f.get("data_type", "string"), _TYPE_RULES["string"])
        extra = ""
        if f.get("data_type") == "enum" and f.get("enum_values"):
            extra = f" — allowed: {', '.join(f['enum_values'])}"
        syn = f", aka: {', '.join(f['synonyms'][:4])}" if f.get("synonyms") else ""
        lines.append(f"- {f['key']} ({f['label']}{syn}) → format: {rule}{extra}")
    field_spec = "\n".join(lines)

    prompt = (
        "You are a meticulous financial-data analyst extracting fields from an Indian "
        "company's financial statements for an AOC-4 MCA filing. The document below was "
        "auto-converted to markdown and may have messy spacing, split table cells, or "
        "inconsistent number/date formats.\n\n"
        "For EACH field listed, find its value in the document and return it CLEANED and "
        "CORRECTLY FORMATTED per the format rule given. Use your judgment to fix obvious "
        "conversion artifacts (missing/extra spaces, comma-grouped digits, currency symbols, "
        "parenthesised negatives, dates in any format). Do NOT invent or estimate values — "
        "if a field genuinely isn't present, omit it. Do NOT include commentary.\n\n"
        "Return a JSON object mapping field key to cleaned value (as a string).\n\n"
        f"Fields to extract:\n{field_spec}\n\n"
        f"Document content:\n{markdown_text[:120000]}"
    )

    # _json_result already unwraps the CLI's occasional template-placeholder
    # artifact, so one call almost always suffices. Keep a light 2-attempt
    # safety net (keep the better) for genuine transient empties, filtering to
    # real schema keys so any residual junk key never counts.
    valid_keys = {f["key"] for f in all_fields}
    best: dict = {}
    for _ in range(2):
        data = _run_claude([
            "-p",
            "--output-format", "json",
            "--tools", "",
            "--json-schema", '{"type":"object","additionalProperties":{"type":"string"}}',
            "--model", _CLAUDE_MODEL,
        ], timeout=240, prompt=prompt)
        result = {k: v for k, v in _json_result(data).items() if k in valid_keys}
        if len(result) > len(best):
            best = result
        if len(best) >= 8:  # a healthy full-statement response; no need to retry
            break
    return best
