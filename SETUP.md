# AOC-4 Data Extractor — Setup & Usage Guide

Reads financial documents from client folders, extracts AOC-4 fields (Balance
Sheet, P&L, Audit, Board Report), and writes both `extracted.json` and a
human-editable Excel file per client so you can review and fix anything before
filing on the MCA portal.

---

## Folder structure (per client)

```
D:\Data\
  ATS System Pvt Ltd_U74999MH2020PTC123456\      <- "ClientName_CIN"
    data\                                         <- files to extract fields from
      balance_sheet.pdf
      profit_loss.xlsx
      auditors_report.docx
      directors_report.pdf
    attachments\                                  <- files uploaded as-is to MCA (not parsed)
      signed_balance_sheet.pdf
      aoc2.pdf
  Another Company Ltd_U12345DL2019PTC654321\
    data\
      ...
    attachments\
      ...
```

- The client folder name must end with the company's 21-character CIN (e.g.
  `..._U74999MH2020PTC123456`) so filings are matched by CIN automatically. If
  you forget, the tool still works — it falls back to reading the CIN from the
  documents themselves and flags a warning.
- `data\` can contain files directly (single filing period) or year subfolders
  (e.g. `data\2024-25\...`) if you're processing multiple years for one client.
- Older folder layouts (`Client\Date\files` or `Client\files`, no CIN) are still
  supported for backward compatibility.

---

## Step 1 — Install Python 3.11+ and Node.js 18+

Python: https://www.python.org/downloads/ (check "Add Python to PATH")
Node.js: https://nodejs.org/

## Step 2 — Create the virtual environment and install packages (one time only)

```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Step 3 — Install Tesseract + Poppler (one time only, needed for scanned PDFs)

- Tesseract: https://github.com/UB-Mannheim/tesseract/wiki — add install dir to PATH
- Poppler: https://github.com/oschwartz10612/poppler-windows/releases — add `bin\` to PATH

Without these, the tool still works for digital PDFs, Excel, Word, and CSV —
only scanned/image PDFs need them.

## Step 4 — (Optional) Enable Claude for cleaner data

The tool always runs a free local regex/heuristic pass first. Claude then adds
accuracy on top. It uses the **Claude Code CLI** (`claude`) directly — not the
pay-per-token Anthropic API — so it runs on whatever account Claude Code is
logged into (a claude.ai Max/Pro subscription's included usage, no API key or
billing). It's off by default. There are two levels:

**Gap-fill mode** — Claude only fills fields the free pass missed; it leaves the
regex-extracted values untouched:

```powershell
$env:AOC4_ALLOW_CLAUDE = "1"
```

**Full-structuring mode (recommended if you have Max)** — Claude reads the whole
document and re-extracts EVERY field cleanly: proper number formatting (strips
`₹`, commas), ISO dates (`2025-03-31`), fixed spacing, normalized values. Its
clean values take precedence over the crude regex output. This is what makes the
data in the Excel/dashboard clean rather than dirty. Set BOTH:

```powershell
$env:AOC4_ALLOW_CLAUDE = "1"
$env:AOC4_CLAUDE_FULL   = "1"
```

Both modes require the `claude` CLI installed and logged in on this machine.
Data leaves the machine only via Claude Code; per Anthropic's terms, data
submitted through Claude Code is not used to train models by default
(see https://privacy.anthropic.com). Everything else — the regex extractors,
markitdown, marker — runs 100% locally.

There's a third, stricter switch for a rare fallback (having Claude directly
read a file that's an unreadable scan even markitdown/marker couldn't handle):

```powershell
$env:AOC4_ALLOW_CLAUDE_FILE_READ = "1"
```

Leave this off unless you specifically want that last-resort path — it runs
Claude with its file-read permission checks bypassed so it can work unattended.

## Step 5 — Run the extractor (command line)

```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION"
python -m extractor "D:\Data"
```

Options: `--verbose` (per-file details), `--client "ATS System"`, `--period "2024-25"`, `--json`.

This writes, per client filing:
- `data\extracted.json` — full machine-readable result
- `D:\Data\finaloutput\<ClientName>_<CIN>.xlsx` — the file you actually work from

## Step 6 — Review and fix in Excel

Open the client's file in `finaloutput\`. It has four sheets:
- **Fields** — every AOC-4 field with value, confidence, source file, and a
  color-coded status (OK / MISSING / LOW-CONFIDENCE / TYPE-ERROR). Edit the
  Value column directly to fix anything.
- **Validation** — missing mandatory fields, low-confidence fields, balance
  sheet / P&L sanity checks, CIN source.
- **Attachments** — files found in `attachments\`, plus a checklist of typical
  AOC-4 attachments to confirm you have everything.
- **Manual Entry** — the 5 fields no document ever contains (email, nature of
  FS, listed status, DIN verification, DSC) — fill these in yourself.

## Step 7 — Run the Web Dashboard (optional, batch view across clients)

**Terminal 1:**
```powershell
.venv\Scripts\Activate.ps1
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION\ui"
python server.py
```

**Terminal 2:**
```powershell
cd "D:\Projects\CS Lalit aUTOFILLING APPLCIATION\ui"
npm install      # first time only
npm run dev
```

Open `http://localhost:5173`, paste the root folder path (e.g. `D:\Data`), and
click Extract. You'll see every client with a status chip:

| Status | Meaning |
|---|---|
| **Ready** | No mandatory gaps, all checks pass, attachments present |
| **Needs Attention** | Missing mandatory fields or a failed sanity check |
| **Missing Attachments** | Fields are fine, but attachments/ is empty |

Click a client to see extracted fields, documents, attachments, and validation
— all read-only. Use **Open Excel** / **Re-validate** to fix cells in Excel and
refresh the status without re-running extraction.

---

## What's NOT automated (by design)

- **MCA login, OTP, captcha** — always manual.
- **DSC signing** — always manual (local emBridge/emSigner + physical DSC token).
- Filling the actual AOC-4 web form on MCA V3 is a separate, later phase (not
  part of this release) — it will stop before sign/submit every time, for the
  same reason.

## Fields extracted

72 AOC-4 fields across Company Info, Balance Sheet (Assets/Equity/Liabilities),
P&L, Prior Year comparatives, Audit, and Board Report. 29 are mandatory —
`missing_mandatory` in the Validation sheet tells you which ones need attention
for a given filing.
