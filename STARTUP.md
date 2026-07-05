# AOC-4 Extractor — Daily Startup Guide

This assumes one-time setup (see `SETUP.md`) is already done — Python, Node,
`.venv`, and `pip install -r requirements.txt` all completed. This doc is just
"how do I start it today."

---

## Option A — Command line only (fastest, no browser)

```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION"
.venv\Scripts\Activate.ps1
python -m extractor "D:\Data" --verbose
```

Then open the client's Excel file in `D:\Data\finaloutput\`.

## Option B — Web Dashboard (see all clients at a glance)

Needs **two terminal windows**, both left open while you work.

**Terminal 1 — API server** (leave running):
```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION"
.venv\Scripts\Activate.ps1
cd ui
python server.py
```

**Terminal 2 — Dashboard**:
```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION\ui"
npm run dev
```

Open **http://localhost:5173** in your browser, paste your data folder path
(e.g. `D:\Data`), click **Extract**.

## Stopping

Press `Ctrl+C` in each terminal window to stop the servers.

---

## (Optional) Turning on Claude for this session

Uses the `claude` CLI you're already logged into (Max/Pro subscription usage,
not paid API billing) — no separate key needed. These reset every time you
close PowerShell — set them again each session, **before** running the
extractor or `server.py`.

For the cleanest data (recommended), enable full-structuring mode — Claude
re-extracts every field cleanly (ISO dates, no ₹/commas, fixed spacing):

```powershell
$env:AOC4_ALLOW_CLAUDE = "1"
$env:AOC4_CLAUDE_FULL   = "1"
```

Or gap-fill only (Claude fills just the missing fields, leaves regex output as-is):

```powershell
$env:AOC4_ALLOW_CLAUDE = "1"
```

Skip both if you don't need it — everything still works on the free local
pass, just with dirtier data and more manual fixing in Excel.

---

## Quick troubleshooting

| Symptom | Check |
|---|---|
| `'python' is not recognized` | Python not on PATH, or you forgot `.venv\Scripts\Activate.ps1` |
| Dashboard page loads but Extract does nothing / errors | Terminal 1 (API server) isn't running, or crashed — check its window for errors |
| `No matching filing folders found` | Folder doesn't match the `ClientName_CIN\data\` convention — see `SETUP.md` |
| PDF shows 0 fields extracted | Likely a scanned PDF — confirm Tesseract + Poppler are installed and on PATH (SETUP.md Step 3) |
| Port 8000 or 5173 already in use | A previous server session is still running somewhere — close that terminal/window first |
