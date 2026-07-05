# AOC-4 form-fill procedure (for Claude, via the browser extension)

This is the exact procedure Claude follows to fill an AOC-4 form (the mock
`/test-form`, or the real MCA V3 portal) from the app's already-extracted data.

**How it is triggered:** a human tells Claude, e.g. *"Fill Acme on the open
form."* A web-page button CANNOT trigger this — the extension only acts on a
human instruction. A button in the app can, at most, open the form and copy this
kind of instruction to the clipboard to paste.

**Trigger phrase (paste into the Claude side-panel, or say in Claude Code):**

> Fill "<CLIENT NAME>" on the open AOC-4 form. Use the procedure in
> filing/FILL_INSTRUCTIONS.md.

## Procedure

1. **Get the data** — fetch `http://localhost:8000/api/clients/<client_id>/fill-data`.
   Look up `<client_id>` from `GET /api/clients` by name if you only have the name.
   The response gives `filings[0].fields` = an ordered list of
   `{key, label, value, section, source}`, and `filings[0].attachments` =
   `{name, size_bytes, path}` for the documents to upload.

2. **Fill each field by its label** — for every field, locate the input on the
   page by its `label` (use `find`/`read_page`), set the `value`
   (`form_input`), and verify it took. Do NOT rely on any pre-mapped selectors —
   match on the visible label so it survives MCA form changes.

3. **Attachments** — for each attachment, find the matching upload input by file
   name and attach the file at `path`. NOTE: the current extension build may
   reject uploading by host path; if so, tell the user to attach these files
   manually (list the names + paths) and continue.

4. **Verify, then STOP** — confirm the filled values look right and report a
   summary. **Never** click DSC-sign or Submit, and never handle login/OTP —
   those stay with the user.

## Preconditions
- The client has been extracted (green/amber status) and any MANUAL fields are
  saved in the Manual Entry tab — `fill-data` merges those automatically.
- The Claude data-cleaning badge in the dashboard reads **"clean structuring"**
  (server started with `AOC4_ALLOW_CLAUDE=1` + `AOC4_CLAUDE_FULL=1`); otherwise
  the values are raw regex and may be dirty.
- For the real MCA form: the user is already logged in in their own Chrome.
