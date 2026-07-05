"""
Explicit client registry — an alternative to (and layered over) folder scanning.

Each client is an entry with its own name, CIN, and data-folder path, persisted
to clients.json. This lets the dashboard add / edit / remove clients that live in
different locations, rather than requiring every client to sit under one shared
root in the ClientName_CIN layout.

Registry file default location: <project_root>/clients.json
Schema:
  {"clients": [
     {"id": "<stable-id>", "name": "...", "cin": "...", "path": "D:\\...\\data-or-client-folder"},
     ...
  ]}

A client's `path` may point either at a folder that directly holds the source
documents, or at a ClientName_CIN folder containing data/ + attachments/ — the
scanner handles both, so both work here.
"""
import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = _PROJECT_ROOT / "clients.json"

_CIN_RE = re.compile(r'^[A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$')


def _slug(name: str, cin: str | None) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-') or 'client'
    return f"{base}-{(cin or 'no-cin').lower()}"


def load_clients(path: Path = REGISTRY_PATH) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        clients = data.get("clients", [])
        return clients if isinstance(clients, list) else []
    except Exception:
        return []


def save_clients(clients: list[dict], path: Path = REGISTRY_PATH) -> None:
    Path(path).write_text(
        json.dumps({"clients": clients}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def validate_client(name: str, cin: str, path: str) -> str | None:
    """Return an error message if invalid, else None."""
    if not (name or "").strip():
        return "Client name is required."
    if not (path or "").strip():
        return "Data folder path is required."
    if not Path(path).is_dir():
        return f"Folder not found: {path}"
    if cin and not _CIN_RE.match(cin.strip().upper()):
        return "CIN must be 21 characters, e.g. U74999MH2020PTC123456 (or leave blank)."
    return None


def add_client(name: str, cin: str, path: str, registry: Path = REGISTRY_PATH) -> dict:
    clients = load_clients(registry)
    cin = (cin or "").strip().upper() or None
    entry = {"id": _slug(name, cin), "name": name.strip(), "cin": cin, "path": path.strip()}
    # Replace an existing entry with the same id (same name+cin) rather than duplicate.
    clients = [c for c in clients if c.get("id") != entry["id"]]
    clients.append(entry)
    save_clients(clients, registry)
    return entry


def update_client(client_id: str, name: str, cin: str, path: str, registry: Path = REGISTRY_PATH) -> dict | None:
    clients = load_clients(registry)
    cin = (cin or "").strip().upper() or None
    for c in clients:
        if c.get("id") == client_id:
            c["name"] = name.strip()
            c["cin"] = cin
            c["path"] = path.strip()
            save_clients(clients, registry)
            return c
    return None


def remove_client(client_id: str, registry: Path = REGISTRY_PATH) -> bool:
    clients = load_clients(registry)
    new = [c for c in clients if c.get("id") != client_id]
    if len(new) == len(clients):
        return False
    save_clients(new, registry)
    return True
