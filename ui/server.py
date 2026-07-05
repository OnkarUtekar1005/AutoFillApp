"""FastAPI backend for the AOC-4 extractor dashboard."""
import sys
import os
import json
import time
import itertools
import threading

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
# Add project root to path so `extractor` package is importable
sys.path.insert(0, _PROJECT_ROOT)

import html as _html

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from extractor.ingestion.folder_scanner import scan_root
from extractor.ingestion.pipeline import (
    revalidate_from_excel,
    process_client_entry, load_cached_client, apply_manual_and_revalidate,
)
from extractor.ingestion import client_registry as registry
from extractor.ingestion import manual_values
from extractor.extraction import llm_gapfill
from extractor.mapping.schema import FIELD_BY_KEY, AOC4_FIELDS, SECTIONS

app = FastAPI(title="AOC-4 Extractor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImportRequest(BaseModel):
    folder: str


class RevalidateRequest(BaseModel):
    excel_path: str


class ClientRequest(BaseModel):
    name: str
    cin: str | None = None
    path: str


class ManualRequest(BaseModel):
    client_id: str
    values: dict


class FillRequestBody(BaseModel):
    client_id: str


class FillDoneBody(BaseModel):
    worker: str | None = None
    ok: bool = True
    message: str | None = None


@app.get("/api/schema")
def schema():
    """Field metadata so the dashboard can render editable inputs (esp. MANUAL
    fields) and section labels without hard-coding the 273-field list."""
    return {
        "sections": SECTIONS,
        "fields": [
            {
                "key": f.key, "label": f.label, "section": f.section,
                "data_type": f.data_type, "source": f.source,
                "mandatory": f.mandatory, "enum_values": f.enum_values,
            }
            for f in AOC4_FIELDS
        ],
    }


@app.post("/api/manual")
def save_manual(req: ManualRequest):
    """Persist MANUAL field values the user typed in the dashboard (keyed by
    CIN), then re-merge + re-validate the client's cached result and return it."""
    entry = next((c for c in registry.load_clients() if c.get("id") == req.client_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Client not found")
    manual_values.set_for(entry.get("cin"), entry.get("name"), req.values)

    out = []
    for r in load_cached_client(entry):
        updated = apply_manual_and_revalidate(r, entry.get("cin"), entry.get("name"))
        out.append(_serialize(updated))
    return {"filings": out}


def _error_filing(entry: dict, err: str) -> dict:
    return {
        "client_name": entry.get("name", "Unknown"),
        "cin": entry.get("cin"),
        "cin_source": "registry",
        "period": "Unknown period",
        "folder_path": entry.get("path", ""),
        "status": "Needs Attention",
        "total_fields_extracted": 0,
        "fields": {},
        "documents": [{"file_path": entry.get("path", ""), "ingest_path": "ERROR", "status": "error", "error": err}],
        "validation": {},
        "attachments": [],
        "excel_path": None,
    }


# ── Client registry CRUD ──────────────────────────────────────────────────

@app.get("/api/clients")
def list_clients():
    return {"clients": registry.load_clients()}


@app.post("/api/clients")
def add_client(req: ClientRequest):
    err = registry.validate_client(req.name, req.cin or "", req.path)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"client": registry.add_client(req.name, req.cin or "", req.path)}


@app.put("/api/clients/{client_id}")
def update_client(client_id: str, req: ClientRequest):
    err = registry.validate_client(req.name, req.cin or "", req.path)
    if err:
        raise HTTPException(status_code=400, detail=err)
    updated = registry.update_client(client_id, req.name, req.cin or "", req.path)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"client": updated}


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str):
    if not registry.remove_client(client_id):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}


@app.post("/api/clients/import")
def import_clients(req: ImportRequest):
    """Scan a root folder and add each discovered ClientName_CIN folder to the
    registry as a client (bulk add). Returns the updated client list."""
    folder = req.folder.strip().strip("'\"")
    if not os.path.isdir(folder):
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder}")
    try:
        filings = scan_root(folder)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Folder scan failed: {e}")

    added = 0
    for f in filings:
        registry.add_client(f.client_name, f.cin or "", str(f.folder_path))
        added += 1
    return {"added": added, "clients": registry.load_clients()}


# ── Extraction over the registry (async background jobs) ──────────────────
#
# Extraction can take minutes (large scanned PDFs + Claude full mode). Running
# it inline made the HTTP request hang and the UI spinner never resolve. Instead
# we run it on a background thread and expose a job the frontend polls, so the
# dashboard knows exactly when a run is in progress vs. done — and updates itself
# without a manual refresh.

_jobs: dict = {}
_jobs_lock = threading.Lock()


def _set_job(key: str, **kw):
    with _jobs_lock:
        _jobs[key] = {**_jobs.get(key, {}), **kw}


def _extract_entries_job(key: str, entries: list):
    out = []
    total = len(entries)
    for i, entry in enumerate(entries):
        _set_job(key, status="running",
                 progress={"done": i, "total": total, "current": entry.get("name")})
        try:
            client_results = process_client_entry(entry, _PROJECT_ROOT, verbose=False)
            if not client_results:
                out.append(_error_filing(entry, "No supported documents found at this path."))
            for r in client_results:
                out.append(_serialize(r))
        except Exception as e:
            out.append(_error_filing(entry, str(e)))
    _set_job(key, status="done", filings=out,
             progress={"done": total, "total": total, "current": None})


def _start_job(key: str, entries: list):
    _set_job(key, status="running", filings=None, error=None,
             progress={"done": 0, "total": len(entries), "current": None})
    threading.Thread(target=_extract_entries_job, args=(key, entries), daemon=True).start()


@app.get("/api/state")
def state():
    """Dashboard landing data: registered clients and their cached results
    (replayed from extracted.json, no re-extraction)."""
    clients = registry.load_clients()
    filings = []
    for entry in clients:
        try:
            for r in load_cached_client(entry):
                filings.append(_serialize(r))
        except Exception:
            pass
    return {"clients": clients, "filings": filings, "claude": llm_gapfill.claude_status()}


@app.get("/api/claude-status")
def claude_status():
    """Whether Claude data-cleaning is active in THIS server process, so the
    dashboard can show an enabled/disabled badge. Read live from env each call."""
    return llm_gapfill.claude_status()


@app.post("/api/extract")
def extract():
    """Start a background job extracting every registered client. Poll
    /api/jobs/__all__ for progress + results."""
    _start_job("__all__", registry.load_clients())
    return {"job": "__all__"}


@app.post("/api/clients/{client_id}/extract")
def extract_one(client_id: str):
    """Start a background job extracting one client. Poll /api/jobs/<id>."""
    entry = next((c for c in registry.load_clients() if c.get("id") == client_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Client not found")
    _start_job(client_id, [entry])
    return {"job": client_id}


@app.get("/api/jobs/{job_key:path}")
def job_status(job_key: str):
    with _jobs_lock:
        return _jobs.get(job_key, {"status": "unknown"})


# ── Fill-request queue ──────────────────────────────────────────────────────
# The dashboard button ENQUEUES a fill job here; up to two running Claude Code
# "filler" sessions (each with its own Chrome extension) poll /next, fill the
# form via the extension, and POST /done. A web page can't drive the extension,
# but it can drop a job that a trusted agent session picks up. Dequeue is atomic
# under _fill_lock so two workers never grab the same job.
_FILL_STORE = os.path.join(_PROJECT_ROOT, "fill_queue.json")
_fill_lock = threading.Lock()
_fill_id = itertools.count(1)
_fill_queue: list[dict] = []
_LEASE_SECONDS = 300  # a job stuck 'in_progress' longer than this can be re-leased (crashed worker)


def _fill_save_locked():
    try:
        with open(_FILL_STORE, "w", encoding="utf-8") as f:
            json.dump(_fill_queue, f, indent=2)
    except OSError:
        pass


def _fill_load():
    global _fill_queue, _fill_id
    try:
        with open(_FILL_STORE, encoding="utf-8") as f:
            _fill_queue = json.load(f)
        _fill_id = itertools.count(max((j["id"] for j in _fill_queue), default=0) + 1)
    except (OSError, ValueError):
        _fill_queue = []


_fill_load()


@app.post("/api/fill-request")
def fill_request(req: FillRequestBody):
    """Queue a client to be auto-filled by a running filler session. No paste."""
    entry = next((c for c in registry.load_clients() if c.get("id") == req.client_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Client not found")
    with _fill_lock:
        job = {
            "id": next(_fill_id), "client_id": entry["id"], "client_name": entry.get("name"),
            "status": "pending", "worker": None, "message": None,
            "created": time.time(), "updated": time.time(),
        }
        _fill_queue.append(job)
        _fill_save_locked()
    return job


@app.get("/api/fill-request/next")
def fill_request_next(worker: str = "worker"):
    """Atomically lease the oldest pending job to a filler session (or re-lease a
    stalled one). Returns {} when the queue is empty."""
    now = time.time()
    with _fill_lock:
        job = next((j for j in _fill_queue if j["status"] == "pending"), None)
        if job is None:
            job = next((j for j in _fill_queue
                        if j["status"] == "in_progress" and now - j["updated"] > _LEASE_SECONDS), None)
        if job is None:
            return {}
        job.update(status="in_progress", worker=worker, updated=now)
        _fill_save_locked()
        return job


@app.post("/api/fill-request/{job_id}/done")
def fill_request_done(job_id: int, body: FillDoneBody):
    """A filler session reports a job finished (ok) or failed."""
    with _fill_lock:
        job = next((j for j in _fill_queue if j["id"] == job_id), None)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        job.update(status="done" if body.ok else "error",
                   message=body.message, updated=time.time())
        _fill_save_locked()
        return job


@app.get("/api/fill-requests")
def fill_requests():
    """The whole queue, newest first — for a dashboard status panel."""
    with _fill_lock:
        return {"requests": sorted(_fill_queue, key=lambda j: j["id"], reverse=True)}


@app.delete("/api/fill-request/{job_id}")
def fill_request_delete(job_id: int):
    """Remove one job from the queue regardless of status (cancel a pending job,
    kill a stuck in_progress one, or delete a finished row)."""
    global _fill_queue
    with _fill_lock:
        before = len(_fill_queue)
        _fill_queue = [j for j in _fill_queue if j["id"] != job_id]
        if len(_fill_queue) == before:
            raise HTTPException(status_code=404, detail="Job not found")
        _fill_save_locked()
        return {"removed": job_id, "requests": sorted(_fill_queue, key=lambda j: j["id"], reverse=True)}


@app.post("/api/fill-requests/clear")
def fill_requests_clear(scope: str = "finished"):
    """Clear the queue. scope=finished (default) drops done/error only;
    scope=all wipes everything (pending + in_progress too)."""
    global _fill_queue
    with _fill_lock:
        if scope == "all":
            _fill_queue = []
        else:
            _fill_queue = [j for j in _fill_queue if j["status"] in ("pending", "in_progress")]
        _fill_save_locked()
        return {"requests": sorted(_fill_queue, key=lambda j: j["id"], reverse=True)}


@app.post("/api/revalidate")
def revalidate(req: RevalidateRequest):
    excel_path = req.excel_path.strip().strip("'\"")
    if not os.path.isfile(excel_path):
        raise HTTPException(status_code=400, detail=f"Excel file not found: {excel_path}")
    try:
        result = revalidate_from_excel(excel_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Revalidate failed: {e}")
    return result


@app.get("/api/download-excel")
def download_excel(path: str):
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))


def _fill_list(fields: dict) -> list[dict]:
    """Ordered, fill-ready field list (schema order) — only fields that have a
    value. This is what Claude reads to type into the MCA form via the browser
    extension. MCA/office-use fields are excluded (portal generates them)."""
    out = []
    for fdef in AOC4_FIELDS:
        info = fields.get(fdef.key)
        val = info.get("value") if info else None
        if val in (None, "") or fdef.source == "MCA":
            continue
        out.append({
            "key": fdef.key, "label": fdef.label, "value": val,
            "section": SECTIONS.get(fdef.section, fdef.section), "source": fdef.source,
        })
    return out


def _live_attachments(entry: dict) -> list[dict]:
    """Scan the client's attachments/ folder right now and return each file with
    its absolute path, so the Claude extension can actually upload it. Reading
    live (not from cached extracted.json) means the list always matches what's on
    disk and always carries a path, even for pre-existing caches."""
    from extractor.ingestion.folder_scanner import scan_client_folder
    out: list[dict] = []
    try:
        for filing in scan_client_folder(entry.get("path"), entry.get("name"), entry.get("cin")):
            for f in getattr(filing, "attachment_files", []) or []:
                try:
                    out.append({"name": f.name, "size_bytes": f.stat().st_size,
                                "extension": f.suffix.lower(), "path": str(f.resolve())})
                except OSError:
                    continue
    except Exception:
        return []
    return out


_TEST_FORM_STYLE = """
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { font-family: system-ui, 'Segoe UI', sans-serif; margin: 0; background: #f6f7f9; color: #111; }
  header { position: sticky; top: 0; z-index: 5; background: #fff; border-bottom: 1px solid #e5e7eb; padding: 12px 20px; display: flex; gap: 12px 16px; align-items: center; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0; }
  header .who { font-size: 13px; color: #334155; margin-right: auto; }
  header .who b { color: #111; }
  main { max-width: 900px; margin: 0 auto; padding: 20px; }
  section { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px; }
  section h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: #64748b; margin: 0 0 12px; }
  .row { display: grid; grid-template-columns: 1fr; gap: 4px; margin-bottom: 10px; }
  label { font-size: 13px; color: #334155; }
  input { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid #cbd5e1; width: 100%; background: #fff; color: #111; }
  input.filled { border-color: #16a34a; background: #f0fdf4; color: #052e16; font-weight: 600; }
  .b { font-size: 10px; padding: 1px 5px; border-radius: 6px; vertical-align: middle; }
  .b.auto { background: #ede9fe; color: #6d28d9; }
  .b.manual { background: #dbeafe; color: #1d4ed8; }
  .badge { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid transparent; }
  .badge.idle { background: #f1f5f9; color: #475569; border-color: #e2e8f0; }
  .badge.pending { background: #fef9c3; color: #854d0e; border-color: #fde68a; }
  .badge.progress { background: #dbeafe; color: #1d4ed8; border-color: #bfdbfe; }
  .badge.done { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
  .badge.error { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
  .count { font-size: 12px; color: #64748b; }
"""


def _test_form_no_client() -> HTMLResponse:
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AOC-4 Test Form</title><style>{_TEST_FORM_STYLE}</style></head><body>
<main><section><h2>AOC-4 Test Form</h2>
<p>This form is scoped to one client. Open it for a specific client from the
dashboard (the <b>Test form</b> action), or add <code>?client=&lt;client_id&gt;</code>
to the URL. It has no autofill button — a running Claude Code filler session fills
it via the browser extension after you click <b>Auto-fill (agent)</b> on the
dashboard.</p></section></main></body></html>"""
    return HTMLResponse(html)


@app.get("/test-form", response_class=HTMLResponse)
def test_form(client: str = ""):
    """A mock AOC-4 form scoped to ONE client, for testing the agent-driven fill
    (queue -> filler session -> browser extension) WITHOUT touching real MCA.
    There is intentionally NO autofill button and NO client picker: the form is a
    passive target that a filler session fills by label. It shows a live status
    of this client's fill job and highlights fields green as they get filled."""
    entry = next((c for c in registry.load_clients() if c.get("id") == client), None)
    if not entry:
        return _test_form_no_client()

    # Empty labeled inputs, grouped by section (schema order) — the fill target.
    groups: list[tuple[str, list]] = []
    seen: dict[str, list] = {}
    for f in AOC4_FIELDS:
        if f.source == "MCA":
            continue
        if f.section not in seen:
            seen[f.section] = []
            groups.append((f.section, seen[f.section]))
        seen[f.section].append(f)

    blocks = []
    for section, fields in groups:
        rows = []
        for f in fields:
            label = _html.escape(f.label)
            badge = "manual" if f.source == "MANUAL" else "auto"
            rows.append(
                f'<div class="row"><label for="{f.key}">{label} '
                f'<span class="b {badge}">{f.source}</span></label>'
                f'<input id="{f.key}" name="{f.key}" data-key="{f.key}" autocomplete="off"></div>'
            )
        blocks.append(
            f'<section><h2>{_html.escape(SECTIONS.get(section, section))}</h2>{"".join(rows)}</section>'
        )

    # Attachments (upload) — rendered server-side for THIS client, since the form
    # is client-scoped. File inputs the extension attaches into by name.
    atts = _live_attachments(entry)
    if atts:
        att_rows = "".join(
            f'<div class="row"><label for="att_{i}">{_html.escape(a["name"])} '
            f'<span class="b auto">{a["size_bytes"]} B</span></label>'
            f'<input type="file" id="att_{i}" aria-label="{_html.escape(a["name"])}" '
            f'data-filename="{_html.escape(a["name"])}"></div>'
            for i, a in enumerate(atts)
        )
        att_note = "Attach each file below (the extension uploads by label)."
    else:
        att_rows = ""
        att_note = "No attachments cataloged for this client."
    blocks.append(f'<section><h2>Attachments (upload)</h2>'
                  f'<p style="font-size:13px;color:#64748b;margin:0 0 10px">{att_note}</p>{att_rows}</section>')

    name = _html.escape(entry.get("name") or "Unknown client")
    cin = _html.escape(entry.get("cin") or "no CIN")
    client_json = json.dumps(client)
    body = "".join(blocks)
    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AOC-4 Test Form — {name}</title>
<style>{_TEST_FORM_STYLE}</style></head><body>
<header>
  <div class="who">Filling: <b>{name}</b> &nbsp;·&nbsp; <span style="font-family:monospace">{cin}</span></div>
  <span id="fillstatus" class="badge idle">Checking…</span>
  <span id="count" class="count"></span>
</header>
<main>{body}</main>
<script>
const CLIENT_ID = {client_json};
// Highlight any field that has a value (the agent sets values via the extension;
// this sweep marks them green so you can watch the fill happen). No button, no
// self-fill — this form only ever displays what the filler session types in.
function sweep() {{
  let n = 0;
  document.querySelectorAll('main input:not([type=file])').forEach(i => {{
    if (i.value) {{ i.classList.add('filled'); n++; }} else {{ i.classList.remove('filled'); }}
  }});
  document.getElementById('count').textContent = n + ' fields filled';
}}
setInterval(sweep, 800);
// Live status of THIS client's fill job from the queue.
async function pollStatus() {{
  try {{
    const r = await fetch('/api/fill-requests'); const d = await r.json();
    const job = (d.requests || []).find(j => j.client_id === CLIENT_ID); // newest first
    const el = document.getElementById('fillstatus');
    if (!job) {{ el.className = 'badge idle'; el.textContent = 'No fill job — click "Auto-fill (agent)" on the dashboard'; }}
    else if (job.status === 'pending') {{ el.className = 'badge pending'; el.textContent = 'Queued #' + job.id + ' — waiting for a filler'; }}
    else if (job.status === 'in_progress') {{ el.className = 'badge progress'; el.textContent = 'Filling… #' + job.id + ' (worker ' + (job.worker||'?') + ')'; }}
    else if (job.status === 'done') {{ el.className = 'badge done'; el.textContent = 'Filled ✓ #' + job.id + (job.message ? ' — ' + job.message : ''); }}
    else {{ el.className = 'badge error'; el.textContent = 'Error #' + job.id + (job.message ? ' — ' + job.message : ''); }}
  }} catch (e) {{ /* backend momentarily unreachable */ }}
}}
setInterval(pollStatus, 3000); pollStatus();
</script></body></html>"""
    return HTMLResponse(html_doc)


@app.get("/api/clients/{client_id}/fill-data")
def fill_data(client_id: str):
    """The client's fill-ready field values (label → value, in form order). The
    Claude browser extension reads this to fill the MCA V3 form field-by-field
    against the user's already-logged-in Chrome. Login/DSC/submit stay manual."""
    entry = next((c for c in registry.load_clients() if c.get("id") == client_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail="Client not found")
    cin, name = entry.get("cin"), entry.get("name")
    live_attachments = _live_attachments(entry)  # fresh from the attachments/ folder, with paths
    cached = load_cached_client(entry)
    # If never extracted but the CS has saved manual values, still surface those
    # so autofill isn't empty — synthesize a minimal result from manual values.
    if not cached:
        cached = [{"client_name": name, "cin": cin, "period": None,
                   "status": "Needs Attention", "fields": {}}]
    filings = []
    for r in cached:
        # Merge freshly-saved manual values into the cached extraction so newly
        # entered MANUAL fields always appear in autofill (they live in
        # manual_values.json, not necessarily in the cached extracted.json).
        r = apply_manual_and_revalidate(r, cin, name)
        filings.append({
            "client_name": r.get("client_name"),
            "cin": r.get("cin"),
            "period": r.get("period"),
            "status": r.get("status"),
            "fields": _fill_list(r.get("fields", {})),
            # Prefer live folder scan (has absolute paths for the extension to
            # upload); fall back to the cached catalog if the scan found nothing.
            "attachments": live_attachments or r.get("attachments") or [],
        })
    return {"client": entry, "filings": filings}


def _serialize(result: dict) -> dict:
    """Normalize pipeline result into frontend-friendly shape."""
    fields_out = {}
    for key, fd in (result.get("fields") or {}).items():
        fdef = FIELD_BY_KEY.get(key)
        fields_out[key] = {
            "value": fd.get("value"),
            "confidence": fd.get("confidence"),
            "source_file": fd.get("source"),
            "page": fd.get("page"),
            "raw_label": fd.get("raw_label"),
            "section": fdef.section if fdef else None,
            "label": fdef.label if fdef else key,
        }

    docs_out = []
    for doc in (result.get("documents") or []):
        docs_out.append({
            "file_path": doc.get("file"),
            "ingest_path": doc.get("ingest_path"),
            "items_extracted": doc.get("line_items_extracted"),
            "fields_mapped": doc.get("fields_mapped"),
            "status": doc.get("status"),
            "error": doc.get("error"),
        })

    return {
        "client_name": result.get("client_name", "Unknown"),
        "cin": result.get("cin"),
        "cin_source": result.get("cin_source", "not_found"),
        "period": result.get("period") or "Unknown period",
        "folder_path": result.get("folder", ""),
        "status": result.get("status", "Needs Attention"),
        "total_fields_extracted": result.get("total_fields_extracted", len(fields_out)),
        "fields": fields_out,
        "documents": docs_out,
        "validation": result.get("validation") or {},
        "attachments": result.get("attachments") or [],
        "excel_path": result.get("excel_path"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
