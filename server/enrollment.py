"""First sign-in verifies the server and account, then certifies a locally generated device key."""

import hashlib
import json
import re
import secrets
import ssl
import threading

from config import DATA_DIR
from protocol import ProtocolError, receive_frame, send_error, send_frame
from provision import Issuer
from security_audit import record_security_event


class Enrollment:
    def __init__(self, accounts, credentials):
        tools = json.loads((DATA_DIR / "issuer-tool.json").read_text(encoding="utf-8"))
        self.issuer = Issuer(tools["openssl"], initialize=False)
        self.accounts = accounts
        self.credentials = credentials
        self.issuance_lock = threading.Lock()

    def handle(self, connection):
        try:
            kind, status, request = receive_frame(connection)
            encoded = request.get("password_hex")
            csr = request.get("csr_hex")
            if (kind != "ENROLL" or status != 0 or not isinstance(encoded, str) or
                not re.fullmatch(r"(?:[0-9a-f]{2}){1,256}", encoded) or
                not isinstance(csr, str) or not re.fullmatch(r"(?:[0-9a-f]{2}){1,2600}", csr)):
                raise ValueError("invalid enrollment fields")
            self.credentials.verify_executable(request.get("exe_hash"))
            username = request.get("username")
            self.accounts.verify(username, bytes.fromhex(encoded), "node")
            node = "node-" + secrets.token_hex(12)
            with self.issuance_lock:
                certificate = self.issuer.enroll(node, bytes.fromhex(csr))
                fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(certificate)).hexdigest()
                license_id = self.accounts.register_device(node, username, fingerprint)
                token = self.accounts.issue(username, node, fingerprint)
            record_security_event("DEVICE_ENROLLED", node)
            send_frame(connection, "ENROLLED", 200, {
                "node_id": node, "license_id": license_id, "cert_hex": certificate.encode("ascii").hex(),
                "token": token,
            })
        except (ValueError, ProtocolError):
            record_security_event("ENROLLMENT_REJECTED")
            send_error(connection, 401, "enrollment rejected")
        except (RuntimeError, OSError):
            record_security_event("ENROLLMENT_UNAVAILABLE")
            send_error(connection, 503, "enrollment temporarily unavailable")
