# AOC-4 Filing Automation

Extraction + review + assisted-filling pipeline for AOC-4 filings (MCA V3), for a
CA/CS firm. Pulls financial fields out of client documents, lets a human validate
in Excel, and helps auto-fill the MCA form — login, DSC signing, and final submit
always stay manual.

## What it does
1. **Extract** — reads each client's documents (PDF/Excel/Word/CSV/scans) and
   pulls out AOC-4 fields via regex + optional Claude cleaning. Writes a per-client
   Excel for review and a cached `extracted.json`.
2. **Review** — a dashboard shows readiness per client; corrections happen in the
   Excel, then **Re-validate** refreshes status. Manual-only fields are entered
   once and reused.
3. **Fill** — a queue + filler model fills the MCA form (or the local test form)
   field-by-field by label, stopping before DSC/submit:
   - **Extension filler** — a running Claude Code session drives the browser
     extension (free login, no selectors). See `filing/FILL_WATCHER.md`.
   - **Playwright worker** — a standalone service that fills unattended:
     `python -m filing.fill_worker --worker A`.

## Run it
See **`SETUP.md`** (one-time setup) and **`STARTUP.md`** (daily start). Short version:

```powershell
# backend (Claude cleaning on)
cd ui
$env:AOC4_ALLOW_CLAUDE="1"; $env:AOC4_CLAUDE_FULL="1"
python -m uvicorn server:app --host 0.0.0.0 --port 8000
# frontend (separate terminal)
cd ui && npm run dev        # http://localhost:5173
```

Claude cleaning uses the `claude` CLI (Max/Pro subscription), gated behind two
explicit opt-in env vars for client-data confidentiality — never on by default.

## Layout
- `extractor/` — ingestion, extraction, mapping, validation, Excel output
- `ui/` — FastAPI backend (`server.py`) + React/shadcn dashboard
- `filing/` — fill instructions, watcher docs, Playwright worker
- `AOC4_FORM_FIELDS.md` — the full AOC-4 field list (ground truth)

## Note on data
Client documents, extracted values, and generated Excels are **confidential** and
are excluded from git via `.gitignore` (`sample_data/`, `finaloutput/`,
`extracted.json`, `manual_values.json`, `clients.json`, `*.xlsx`). Keep it that way.
