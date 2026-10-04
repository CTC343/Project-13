"""演示节点凭据、许可证和程序完整性白名单。"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from datetime import date
from pathlib import Path

from config import AUTH_TIME_WINDOW_SECONDS, DEMO_CREDENTIAL_COUNT, LICENSE_EXPIRES
from secure_channel import derive_session_key, hmac_hex
from rsa_keys import ensure_task_signing_keys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORE_FILE = PROJECT_ROOT / "data" / "node_credentials.json"
CLIENT_CREDENTIAL_DIR = PROJECT_ROOT / "client" / "credentials"


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_store():
    if not STORE_FILE.exists():
        return {}
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_store(store):
    STORE_FILE.parent.mkdir(exist_ok=True)
    STORE_FILE.write_text(
        json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _write_client_credential(node_id, record):
    CLIENT_CREDENTIAL_DIR.mkdir(exist_ok=True)
    text = (
        "PROJECT13-CREDENTIAL-V1\n"
        f"node_id={node_id}\n"
        f"license_id={record['license_id']}\n"
        f"expires={record['expires']}\n"
        f"auth_key={record['auth_key']}\n"
    )
    (CLIENT_CREDENTIAL_DIR / f"{node_id}.cred").write_text(
        text, encoding="ascii"
    )


def provision_demo_credentials(refresh_hashes=False):
    """首次运行生成随机凭据；重新编译后可显式刷新程序哈希。"""
    ensure_task_signing_keys()
    store = _read_store()
    node_ids = [
        f"node-{index:02d}" for index in range(1, DEMO_CREDENTIAL_COUNT + 1)
    ]
    node_ids.extend(["node-ui", "node-1", "node-2", "node-3"])

    executable_hashes = []
    for name in ("client.exe", "client_gui.exe"):
        path = PROJECT_ROOT / "client" / name
        if path.exists():
            executable_hashes.append(file_sha256(path))

    for node_id in node_ids:
        record = store.get(node_id)
        if record is None:
            record = {
                "license_id": "lic-" + secrets.token_hex(12),
                "expires": LICENSE_EXPIRES,
                "auth_key": secrets.token_hex(32),
                "allowed_exe_hashes": executable_hashes,
            }
            store[node_id] = record
        elif refresh_hashes and executable_hashes:
            record["allowed_exe_hashes"] = executable_hashes
        _write_client_credential(node_id, record)

    _write_store(store)
    return len(store)


class CredentialStore:
    def __init__(self):
        provision_demo_credentials(refresh_hashes=False)
        self.records = _read_store()
        self.used_nonces = {}
        self.lock = threading.Lock()

    def _remove_old_nonces(self, now):
        oldest = now - AUTH_TIME_WINDOW_SECONDS * 2
        self.used_nonces = {
            nonce: seen_at for nonce, seen_at in self.used_nonces.items()
            if seen_at >= oldest
        }

    def authenticate(self, request):
        try:
            node_id = request["node_id"]
            license_id = request["license_id"]
            timestamp = int(request["timestamp"])
            client_nonce = request["client_nonce"]
            exe_hash = request["exe_hash"]
            received_tag = request["auth_tag"]
            persistent = int(bool(request.get("persistent", False)))
        except (KeyError, TypeError, ValueError):
            raise ValueError("missing authentication field") from None

        if not isinstance(node_id, str) or not node_id:
            raise ValueError("invalid node id")
        if len(client_nonce) != 32 or len(exe_hash) != 64:
            raise ValueError("invalid authentication value length")

        record = self.records.get(node_id)
        if record is None:
            raise ValueError("unknown node identity")
        if license_id != record["license_id"]:
            raise ValueError("license does not belong to node")
        if date.fromisoformat(record["expires"]) < date.today():
            raise ValueError("license has expired")

        now = int(time.time())
        if abs(now - timestamp) > AUTH_TIME_WINDOW_SECONDS:
            raise ValueError("authentication timestamp is outside time window")
        with self.lock:
            self._remove_old_nonces(now)
            if client_nonce in self.used_nonces:
                raise ValueError("authentication replay detected")

        allowed_hashes = record.get("allowed_exe_hashes", [])
        if allowed_hashes and exe_hash not in allowed_hashes:
            raise ValueError("client executable integrity check failed")

        auth_key = bytes.fromhex(record["auth_key"])
        auth_text = (
            f"{node_id}|{license_id}|{timestamp}|{client_nonce}|"
            f"{exe_hash}|{persistent}"
        )
        expected_tag = hmac_hex(auth_key, auth_text)
        if not hmac.compare_digest(received_tag, expected_tag):
            raise ValueError("identity authentication failed")

        with self.lock:
            if client_nonce in self.used_nonces:
                raise ValueError("authentication replay detected")
            self.used_nonces[client_nonce] = now
        return auth_key

    def create_session(self, auth_key, client_nonce):
        session_id = secrets.token_hex(12)
        server_nonce = secrets.token_hex(16)
        session_key = derive_session_key(
            auth_key, client_nonce, server_nonce, session_id
        )
        proof_text = f"SERVER|{session_id}|{client_nonce}|{server_nonce}"
        server_proof = hmac_hex(auth_key, proof_text)
        return session_id, server_nonce, server_proof, session_key
