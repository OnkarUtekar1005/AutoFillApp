"""
Autonomous fill-worker service (Playwright) — the hands-off filler.

Unlike the Claude browser extension (which only works inside a live interactive
agent session), this is a plain background service: it drives its OWN Chromium
via Playwright, so it can run unattended. It polls the fill-request queue and,
for each job, opens that client's form and fills it — no agent, no paste.

For the local **test form** there is no login at all. (Real MCA later would use
a persistent browser profile so a one-time login is reused — not needed here.)

Run:
    python -m filing.fill_worker --worker A
    python -m filing.fill_worker --worker A --headless      # no visible window
    python -m filing.fill_worker --worker A --base http://localhost:8000

Stop with Ctrl+C. Run a second copy with --worker B for parallel filling.
"""
import argparse
import sys
import time
import urllib.request
import urllib.error
import json

from playwright.sync_api import sync_playwright


def _get(url: str):
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(url: str, body: dict):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def _fill_one(page, base: str, job: dict) -> str:
    """Open the client's test form and fill every field + attachment. Returns a
    short summary string for the /done message."""
    client_id = job["client_id"]
    data = _get(f"{base}/api/clients/{client_id}/fill-data")
    filing = (data.get("filings") or [{}])[0]
    fields = filing.get("fields", [])
    attachments = filing.get("attachments", [])

    page.goto(f"{base}/test-form?client={client_id}", wait_until="domcontentloaded")

    filled = 0
    for f in fields:
        # Test-form input id == the field key; fill by id (robust). Label-based
        # matching is what the MCA extension path uses instead.
        loc = page.locator(f"#{f['key']}")
        if loc.count() and loc.first.get_attribute("type") != "file":
            loc.first.fill(str(f["value"]))
            filled += 1

    attached = 0
    for a in attachments:
        path = a.get("path")
        if not path:
            continue
        loc = page.locator(f'input[type=file][data-filename="{a["name"]}"]')
        if loc.count():
            try:
                loc.first.set_input_files(path)   # Playwright CAN upload by path
                attached += 1
            except Exception:
                pass

    return f"{filled} fields, {attached} attachments"


def run(base: str, worker: str, poll: float, headless: bool):
    print(f"[fill-worker {worker}] starting — base={base} headless={headless}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            while True:
                try:
                    job = _get(f"{base}/api/fill-request/next?worker={worker}")
                except urllib.error.URLError:
                    print(f"[fill-worker {worker}] backend unreachable, retrying…")
                    time.sleep(poll)
                    continue

                if not job:
                    time.sleep(poll)
                    continue

                print(f"[fill-worker {worker}] job #{job['id']} — {job.get('client_name')}")
                try:
                    summary = _fill_one(page, base, job)
                    _post(f"{base}/api/fill-request/{job['id']}/done",
                          {"worker": worker, "ok": True, "message": summary})
                    print(f"[fill-worker {worker}] job #{job['id']} done — {summary}")
                except Exception as exc:
                    _post(f"{base}/api/fill-request/{job['id']}/done",
                          {"worker": worker, "ok": False, "message": str(exc)[:200]})
                    print(f"[fill-worker {worker}] job #{job['id']} FAILED — {exc}")
        except KeyboardInterrupt:
            print(f"\n[fill-worker {worker}] stopping.")
        finally:
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Playwright fill-worker for the AOC-4 queue")
    ap.add_argument("--base", default="http://localhost:8000", help="backend base URL")
    ap.add_argument("--worker", default="A", help="worker name (use A and B for two)")
    ap.add_argument("--poll", type=float, default=3.0, help="seconds between polls when idle")
    ap.add_argument("--headless", action="store_true", help="run without a visible window")
    args = ap.parse_args()
    run(args.base, args.worker, args.poll, args.headless)


if __name__ == "__main__":
    sys.exit(main())
