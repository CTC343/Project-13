"""Project13 listener. Control-center requests arrive over the local data directory."""

from concurrent.futures import ThreadPoolExecutor
import json
import re
import select
import socket
import ssl
import threading

from accounts import AccountStore
from config import DATA_DIR, HOST, MAX_CONCURRENT_CLIENTS, PORT, SOCKET_TIMEOUT_SECONDS
from credential_store import CredentialStore
from enrollment import Enrollment
from node_registry import NodeRegistry
from preview import PreviewBroker
from protocol import ProtocolError, receive_frame, send_error
from rsa_keys import read_private_key
from security_audit import record_security_event
from task_service import handle_client
from task_state import TaskState
from tls_transport import server_context

COMMAND_DIR = DATA_DIR / "commands"
AEAD_SUITES = {"TLS_AES_256_GCM_SHA384", "TLS_AES_128_GCM_SHA256"}


def consume_commands(state):
    for command in sorted(COMMAND_DIR.glob("*.json")):
        try:
            if not re.fullmatch(r"[a-f0-9]{32}", command.stem):
                raise ValueError("invalid request ID")
            request = json.loads(command.read_text(encoding="utf-8"))
            if request.get("role") != "operator":
                raise ValueError("operator role required")
            state.start_batch(request["settings"], command.stem)
            record_security_event("BATCH_STARTED", request["actor"], "local", command.stem)
            print(f"Batch started: {state.get_task_id()}", flush=True)
        except (ValueError, KeyError, TypeError) as error:
            print(f"Batch rejected: {error}", flush=True)
        command.unlink(missing_ok=True)


def serve(server_socket, registration_socket, context, registration_context, state, credentials, accounts):
    registry = NodeRegistry()
    preview = PreviewBroker()
    enrollment = Enrollment(accounts, credentials)
    preview_capacity = threading.BoundedSemaphore(2)
    capacity = threading.BoundedSemaphore(MAX_CONCURRENT_CLIENTS)
    business_connections = threading.BoundedSemaphore(MAX_CONCURRENT_CLIENTS + 2)
    registration_capacity = threading.BoundedSemaphore(8)

    def run_client(client_socket, enrolling, slots):
        try:
            with client_socket:
                client_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
                tls_context = registration_context if enrolling else context
                with tls_context.wrap_socket(client_socket, server_side=True) as encrypted:
                    if encrypted.cipher()[0] not in AEAD_SUITES:
                        raise ssl.SSLError("unsupported cipher suite")
                    if enrolling:
                        enrollment.handle(encrypted)
                    else:
                        request = receive_frame(encrypted)
                        is_preview = request[0] == "PREVIEW_OPEN"
                        workers_for_type = preview_capacity if is_preview else capacity
                        if not workers_for_type.acquire(blocking=False):
                            send_error(encrypted, 503, "connection capacity reached")
                            return
                        try:
                            if is_preview:
                                preview.serve(encrypted, *request[1:], accounts, credentials)
                            else:
                                handle_client(encrypted, state, credentials, accounts, registry, request, preview)
                        finally:
                            workers_for_type.release()
        except ProtocolError:
            record_security_event("REQUEST_REJECTED", detail="invalid initial frame")
        except (ssl.SSLError, OSError):
            record_security_event("TLS_REJECTED", detail="handshake or transport rejected")
        finally:
            slots.release()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CLIENTS + 10) as workers:
        while True:
            consume_commands(state)
            preview.refresh()
            readable, _, _ = select.select([server_socket, registration_socket], [], [], 0.5)
            for listener in readable:
                connection, _ = listener.accept()
                enrolling = listener is registration_socket
                slots = registration_capacity if enrolling else business_connections
                if slots.acquire(blocking=False):
                    workers.submit(run_client, connection, enrolling, slots)
                else:
                    connection.close()


def main():
    if not 1 <= PORT < 65535 or not 3 <= MAX_CONCURRENT_CLIENTS <= 512:
        raise ValueError("use service port 1–65534 and capacity 3–512")
    context = server_context()
    registration_context = server_context(enrollment=True)
    credentials = CredentialStore()
    read_private_key()
    accounts = AccountStore()
    state = TaskState()
    COMMAND_DIR.mkdir(exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener, \
         socket.socket(socket.AF_INET, socket.SOCK_STREAM) as registration:
        for sock, port, backlog in ((listener, PORT, MAX_CONCURRENT_CLIENTS), (registration, PORT + 1, 8)):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            sock.bind((HOST, port))
            sock.listen(backlog)
        print(f"READY: {HOST}:{PORT} mTLS, enrollment port {PORT + 1}, capacity {MAX_CONCURRENT_CLIENTS}", flush=True)
        if not state.completed:
            print(f"Batch active: {state.get_task_id()}", flush=True)
        serve(listener, registration, context, registration_context, state, credentials, accounts)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, KeyError) as error:
        print(f"Server setup failed: {error}", flush=True)
        raise SystemExit(1) from None
