"""Approved client build hashes, independent of the number of enrolled devices."""

import hashlib
import json
import os

from config import CLIENT_DIR, DATA_DIR

STORE_FILE = DATA_DIR / "allowed_executables.json"


def file_sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def approve_clients(client_directory=CLIENT_DIR):
    fingerprints = {name: file_sha256(client_directory / name)
                    for name in ("client.exe", "client_gui.exe")}
    temporary = STORE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(fingerprints, indent=2), encoding="utf-8")
    temporary.replace(STORE_FILE)


class CredentialStore:
    def __init__(self):
        from pathlib import Path
        source = Path(os.environ.get("PROJECT13_APPROVED_BUILDS", STORE_FILE))
        self.allowed = frozenset(json.loads(source.read_text(encoding="utf-8")).values())

    def verify_executable(self, fingerprint):
        if not isinstance(fingerprint, str) or fingerprint not in self.allowed:
            raise ValueError("client executable not approved")
