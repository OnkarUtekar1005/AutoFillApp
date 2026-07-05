"""Parse a client folder name of the form 'ClientName_CIN' into (client_name, cin)."""
import re

# CIN: exactly 21 chars — letter, 5 digits, 2 letters, 4 digits, 3 letters, 6 digits
CIN_RE = re.compile(r'([A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})')


def parse_client_folder_name(name: str) -> tuple[str, str | None]:
    """
    Split a folder name like "ATS System Pvt Ltd_L01234MH2020PTC123456"
    into (client_name, cin). Matches the CIN case-insensitively (folder names
    may not be all-caps) but always returns the CIN itself in canonical uppercase.

    If no CIN is found anywhere in the name, returns (name, None) so the caller
    can fall back to extracting the CIN from document text instead.
    """
    upper = name.upper()
    m = CIN_RE.search(upper)
    if not m:
        return name.strip(), None

    cin = m.group(1)
    start = upper.find(cin)
    client_name = name[:start].rstrip(' _-').strip()
    if not client_name:
        client_name = name.strip()
    return client_name, cin
