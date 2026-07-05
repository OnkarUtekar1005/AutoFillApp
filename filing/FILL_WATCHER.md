# Auto-fill watcher — run 1 or 2 Claude Code filler sessions

This is how the dashboard's **"Auto-fill (agent)"** button actually fills a form
with no paste. A web page can't drive the Claude browser extension, but a running
Claude Code session (with the extension paired) can. So the button just **queues**
a job, and a running **filler session** picks it up and fills.

You can run **up to two** filler sessions at once (each with its own Chrome +
extension), so two forms fill in parallel. The queue hands each session a
*different* job — dequeue is atomic, so they never collide.

## Setup (once per filing work-session)

1. Make sure the backend is running with Claude on (badge = "clean structuring").
2. Open the AOC-4 form (test form or the real MCA portal, logged in) in Chrome.
3. Open a Claude Code session that has the **Claude-in-Chrome extension paired**
   (interactive session — a spawned `claude -p` subprocess does NOT get the
   browser tools). Give it the watcher prompt below.
4. (Optional) Repeat in a **second** Chrome window + second Claude Code session
   for parallel filling. Give each a distinct worker name (e.g. `A` and `B`).

## Watcher prompt (paste into each filler session)

> You are an AOC-4 fill worker named "A". Loop: poll
> `GET http://localhost:8000/api/fill-request/next?worker=A`. When it returns a
> job (non-empty), fill that client's AOC-4 form on the open tab following
> `filing/FILL_INSTRUCTIONS.md` (fetch `fill-data` for the job's `client_id`,
> fill every field by label, verify, STOP before DSC/submit). Then POST
> `http://localhost:8000/api/fill-request/<job.id>/done` with
> `{"worker":"A","ok":true,"message":"<n> fields filled"}` (or `ok:false` with
> the error). When `/next` returns `{}`, wait ~10s and poll again.

For the second session, use worker name "B".

Tip: the `/loop` skill can drive the poll cadence, or just let the session loop.

## The queue API (what the button and watcher use)

| Endpoint | Who calls it | Purpose |
|---|---|---|
| `POST /api/fill-request {client_id}` | dashboard button | enqueue a job |
| `GET /api/fill-request/next?worker=<id>` | filler session | atomically lease the next pending job (or re-lease one stalled > 5 min) |
| `POST /api/fill-request/<id>/done {worker, ok, message}` | filler session | report finished / failed |
| `GET /api/fill-requests` | dashboard | list the queue (status panel) |
| `POST /api/fill-requests/clear` | dashboard | drop done/error jobs |

Queue state persists to `fill_queue.json`, so a backend restart keeps pending jobs.

## Boundaries (unchanged)
- Login / OTP / captcha, DSC signing, and final Submit are always manual.
- Attachments: the current extension build can't upload by file path, so the
  filler lists the files to attach and you attach them by hand.
