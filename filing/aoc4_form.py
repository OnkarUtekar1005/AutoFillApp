"""
AOC-4 filing session driver (MCA V3 portal).

WHAT THIS DOES TODAY
--------------------
Launches a real, visible (headed) Chromium browser at the MCA V3 login page and
hands control to the human. YOU log in (credentials, OTP, captcha — never
automated). Once you're logged in, the extracted+cleaned field values for the
selected client are loaded and printed, ready to fill.

WHAT IT DOES NOT DO YET
-----------------------
Auto-typing values into the AOC-4 web form and uploading attachments needs the
form's exact field selectors and upload-slot names, which can only be captured
by walking one real filing on the live MCA V3 portal (the "Step 0 discovery"
session). Until that mapping exists, this driver stops at the point where field
filling would begin, keeps the browser open, and prints the values so you can
fill them manually. When the selector map is added (see FIELD_SELECTORS below),
the same session will fill + verify each field automatically.

ALWAYS MANUAL, BY DESIGN (never automated here)
-----------------------------------------------
  - Login, OTP, captcha
  - DSC signing (local emBridge/emSigner + physical token)
  - Final submit
"""
import sys
from pathlib import Path

MCA_V3_LOGIN_URL = "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/company-forms-download.html"
MCA_V3_HOME_URL = "https://www.mca.gov.in/mcafoportal/login.do"

# To be filled during the Step 0 discovery session on the live portal:
#   {field_key: "css-or-xpath selector for that input on the AOC-4 form"}
# Once populated, fill_fields() will type + verify each value.
FIELD_SELECTORS: dict[str, str] = {}


def _load_field_values(excel_path: Path) -> dict:
    """Read the cleaned field values from the client's finaloutput Excel."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from extractor.output.excel_writer import read_fields_from_excel
    fields = read_fields_from_excel(excel_path)
    return {k: v.get("value") for k, v in fields.items() if v.get("value") not in (None, "")}


def run_filing_session(excel_path: str, url: str = MCA_V3_HOME_URL, headed: bool = True) -> None:
    """
    Open a browser at MCA V3, wait for the human to log in, then load this
    client's data ready to fill. Blocks until the human closes the browser.
    """
    from playwright.sync_api import sync_playwright

    excel = Path(excel_path)
    values = _load_field_values(excel) if excel.exists() else {}

    print("=" * 70)
    print(f"AOC-4 filing session — {excel.stem}")
    print(f"Loaded {len(values)} field values ready to fill.")
    print("=" * 70)
    print("\nOpening MCA V3 in a browser window.")
    print(">>> Please LOG IN manually (credentials, OTP, captcha).")
    print(">>> Login, DSC signing, and final submit are ALWAYS done by you —")
    print("    this tool never handles credentials or clicks submit.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print(f"(Could not preload {url}: {exc} — navigate to the MCA portal manually.)")

        if FIELD_SELECTORS:
            # Selector map exists → fill + verify each field, then STOP before sign/submit.
            print("Filling fields (selector map present)...")
            fill_and_verify(page, values)
            print("\nAll mapped fields filled and verified.")
            print(">>> Review, then sign with DSC and submit YOURSELF. This tool stops here.")
        else:
            # No selector map yet → print values for manual entry, keep browser open.
            print("Field selectors not mapped yet — showing values for manual entry:\n")
            for key, val in values.items():
                print(f"  {key:34} = {val}")
            print("\n>>> Fill these into the AOC-4 form manually.")
            print(">>> To enable auto-fill, run the Step 0 discovery session and")
            print("    populate FIELD_SELECTORS in filing/aoc4_form.py.")

        print("\nBrowser is open. Close the window when you're done to end the session.")
        try:
            # Block until the human closes the browser/page.
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        finally:
            try:
                context.close(); browser.close()
            except Exception:
                pass


def fill_and_verify(page, values: dict) -> None:
    """
    Fill each mapped field, then re-read it from the DOM and compare. Halts the
    whole session on the FIRST mismatch — never silently continues past a field
    that didn't take (matches the 'if copy-paste fails, do not move forward' rule).
    Only runs once FIELD_SELECTORS is populated.
    """
    for key, selector in FIELD_SELECTORS.items():
        if key not in values:
            continue
        want = str(values[key])
        page.fill(selector, want)
        got = page.input_value(selector)
        if got.strip() != want.strip():
            raise RuntimeError(
                f"Field '{key}' did not fill correctly: wanted {want!r}, got {got!r}. Halting."
            )
        print(f"  ✓ {key} = {want}")
