"""
Per-client store for MANUAL field values (the ~74 fields not in any document:
email, authorised capital, type of industry, product ITC codes, service-provider
info, SRNs, etc.).

The CA/CS enters these once in the client's Excel; on Re-validate they're saved
here, keyed by CIN (or name). From then on every extraction and filing merges
them back automatically — so a manual field is typed once, not every year.

Store file: <project_root>/manual_values.json
  { "<CIN>": { "type_of_industry": "...", "company_email": "...", ... }, ... }
"""
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STORE_PATH = _PROJECT_ROOT / "manual_values.json"


def _key(cin: str | None, name: str | None) -> str:
    return ((cin or name or "unknown").strip().upper())


def load_store(path: Path = STORE_PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_for(cin: str | None, name: str | None, path: Path = STORE_PATH) -> dict:
    return load_store(path).get(_key(cin, name), {})


def set_for(cin: str | None, name: str | None, values: dict, path: Path = STORE_PATH) -> None:
    """Merge non-empty values into the stored set for this client (never wipes
    previously-saved values with blanks)."""
    store = load_store(path)
    k = _key(cin, name)
    existing = store.get(k, {})
    existing.update({kk: vv for kk, vv in values.items() if vv not in (None, "")})
    store[k] = existing
    Path(path).write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
