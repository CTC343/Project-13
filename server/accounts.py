"""User credentials and short-lived, certificate-bound reconnect sessions."""

from contextlib import closing
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time

from config import DATA_DIR

ROLES = ("node", "operator", "maintainer", "auditor")
ACCOUNT_ID = re.compile(r"[a-zA-Z0-9_-]{1,63}\Z")
SESSION_SECONDS = 30 * 60
LOGIN_WINDOW = 30
SCRYPT_N = 2**17
SCRYPT_R = 8
SCRYPT_P = 1


def derive(password, salt, n, r, p):
    return hashlib.scrypt(password, salt=salt, n=n, r=r, p=p,
                          dklen=32, maxmem=256 * 1024 * 1024)


class AccountStore:
    def __init__(self):
        self.path = DATA_DIR / "accounts.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.attempt_after = {}
        self.hash_slots = threading.BoundedSemaphore(2)
        self.dummy_salt = secrets.token_bytes(16)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY, role TEXT NOT NULL, node_id TEXT,
                    algorithm TEXT NOT NULL, salt BLOB NOT NULL, digest BLOB NOT NULL,
                    n INTEGER NOT NULL, r INTEGER NOT NULL, p INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    digest BLOB PRIMARY KEY, username TEXT NOT NULL,
                    node_id TEXT NOT NULL, certificate TEXT NOT NULL, expires INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS devices (
                    node_id TEXT PRIMARY KEY, username TEXT NOT NULL,
                    license TEXT NOT NULL, certificate TEXT NOT NULL
                );
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def _password_record(self, username, role, node_id, password):
        if not ACCOUNT_ID.fullmatch(username) or role not in ROLES:
            raise ValueError("invalid username or role")
        if node_id is not None and not ACCOUNT_ID.fullmatch(node_id):
            raise ValueError("invalid node ID")
        if role != "node" and node_id is not None:
            raise ValueError("control-center roles cannot be assigned to a node")
        if not 12 <= len(password) <= 256 or not password.strip():
            raise ValueError("password must have 12–256 UTF-8 bytes")
        salt = secrets.token_bytes(16)
        with self.hash_slots:
            digest = derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
        return username, role, node_id, salt, digest, SCRYPT_N, SCRYPT_R, SCRYPT_P

    def set_password(self, username, role, node_id, password):
        record = self._password_record(username, role, node_id, password)
        with closing(self.connect()) as db, db:
            db.execute("REPLACE INTO accounts VALUES (?, ?, ?, 'scrypt', ?, ?, ?, ?, ?)", record)
            db.execute("DELETE FROM sessions WHERE username = ?", (username,))

    def create_node_account(self, username, password):
        record = self._password_record(username, "node", None, password)
        with closing(self.connect()) as db, db:
            cursor = db.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, 'scrypt', ?, ?, ?, ?, ?) "
                "ON CONFLICT(username) DO NOTHING", record,
            )
            if cursor.rowcount == 0:
                raise ValueError("账号已存在，请使用其他账号名。")

    def list_node_accounts(self):
        accounts = {}
        with closing(self.connect()) as db:
            for username, node_id in db.execute(
                "SELECT accounts.username, devices.node_id FROM accounts "
                "LEFT JOIN devices ON accounts.username = devices.username "
                "WHERE accounts.role = 'node' ORDER BY accounts.username, devices.node_id"
            ):
                nodes = accounts.setdefault(username, [])
                if node_id is not None:
                    nodes.append(node_id)
        return accounts

    def verify(self, username, password, purpose="local"):
        if not isinstance(username, str) or not ACCOUNT_ID.fullmatch(username):
            raise ValueError("invalid login")
        if not 1 <= len(password) <= 256:
            raise ValueError("invalid login")
        now = time.monotonic()
        # Limit peak memory use and pace failed attempts per certified node.
        with self.lock:
            self.attempt_after = {key: value for key, value in self.attempt_after.items() if value > now}
            attempt_key = (purpose, username.casefold())
            if attempt_key in self.attempt_after:
                raise ValueError("login temporarily limited")
            self.attempt_after[attempt_key] = now + LOGIN_WINDOW
        try:
            with self.hash_slots, closing(self.connect()) as db:
                account = db.execute("SELECT role, node_id, algorithm, salt, digest, n, r, p "
                                     "FROM accounts WHERE username = ?", (username,)).fetchone()
                if account is None:
                    derive(password, self.dummy_salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
                    raise ValueError("invalid login")
                role, owner, algorithm, salt, expected, n, r, p = account
                if (algorithm != "scrypt" or (n, r, p) != (SCRYPT_N, SCRYPT_R, SCRYPT_P) or
                        not hmac.compare_digest(derive(password, salt, n, r, p), expected) or
                        (role == "node") != (purpose == "node")):
                    raise ValueError("invalid login")
                with self.lock:
                    self.attempt_after.pop(attempt_key, None)
                return role
        except sqlite3.Error as error:
            raise RuntimeError("credential database unavailable") from error

    def issue(self, username, node_id, certificate):
        token = secrets.token_hex(32)
        now = int(time.time())
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE expires <= ? OR node_id = ?", (now, node_id))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                       (self.token_digest(token), username, node_id, certificate, now + SESSION_SECONDS))
        return token

    @staticmethod
    def token_digest(token):
        if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("invalid session")
        return hashlib.sha256(token.encode("ascii")).digest()

    def resume(self, token, username, node_id, certificate):
        now = int(time.time())
        digest = self.token_digest(token)
        with closing(self.connect()) as db, db:
            record = db.execute(
                "SELECT expires FROM sessions JOIN accounts USING (username) "
                "WHERE sessions.digest = ? AND sessions.username = ? AND sessions.node_id = ? "
                "AND sessions.certificate = ? AND expires > ? AND role = 'node'",
                (digest, username, node_id, certificate, now),
            ).fetchone()
            if record is None:
                raise ValueError("session expired or invalid")
            # An active connection keeps its session. Renew only at the halfway
            # point so each heartbeat does not have to write to the database.
            if record[0] <= now + SESSION_SECONDS // 2:
                db.execute("UPDATE sessions SET expires = ? WHERE digest = ?",
                           (now + SESSION_SECONDS, digest))

    def revoke(self, token):
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM sessions WHERE digest = ?", (self.token_digest(token),))

    def register_device(self, node_id, username, certificate):
        license_id = "lic-" + secrets.token_hex(16)
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO devices VALUES (?, ?, ?, ?)",
                       (node_id, username, license_id, certificate))
        return license_id

    def verify_device(self, node_id, username, presented_license, certificate):
        if not isinstance(username, str) or not isinstance(presented_license, str):
            raise ValueError("invalid device")
        with closing(self.connect()) as db:
            matched = db.execute(
                "SELECT 1 FROM devices JOIN accounts USING (username) WHERE devices.node_id = ? "
                "AND username = ? AND license = ? AND certificate = ? AND role = 'node'",
                (node_id, username, presented_license, certificate),
            ).fetchone()
        if matched is None:
            raise ValueError("unregistered device")
