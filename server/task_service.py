"""Manage node authentication and task messages on a TLS connection."""

import re
import socket
import time

from accounts import ACCOUNT_ID
from config import SOCKET_TIMEOUT_SECONDS
from protocol import (
    ProtocolError, STATUS_CONFLICT, STATUS_OK, STATUS_UNAUTHORIZED,
    receive_frame, send_error, send_frame,
)
from scheduler import release_task, reserve_task
from security_audit import record_security_event
from signature import sign_task
from task_results import store_result
from tls_transport import node_certificate


def _send_secure(client_socket, action, status=STATUS_OK, **values):
    send_frame(client_socket, "SECURE", status, {"action": action, **values})


def _receive_secure(client_socket):
    message_type, status, payload = receive_frame(client_socket)
    if message_type != "SECURE" or status != 0 or not isinstance(payload.get("action"), str):
        raise ProtocolError("invalid business frame")
    return payload


def _heartbeat(socket_value, payload, registry, node_id, preview):
    if payload["action"] != "HEARTBEAT" or type(payload.get("sent_at")) is not int or payload["sent_at"] <= 0:
        raise ProtocolError("expected valid HEARTBEAT")
    registry.update(node_id, "-", "authenticated", "heartbeat")
    view_id = preview.offer(node_id, payload.get("preview_enabled") in (True, 1))
    _send_secure(socket_value, "HEARTBEAT_ACK", server_time=int(time.time()), preview_id=view_id)


def handle_client(client_socket, task_state, credentials, accounts, registry, initial_frame, preview):
    node_id = "-"
    claimed = False
    signed_in = False
    reserved_task = None
    token = ""
    client_socket.settimeout(SOCKET_TIMEOUT_SECONDS)

    try:
        message_type, status, auth = initial_frame
        if message_type != "AUTH" or status != 0:
            raise ProtocolError("expected AUTH", STATUS_UNAUTHORIZED)
        requested_node = auth.get("node_id")
        if not isinstance(requested_node, str) or not ACCOUNT_ID.fullmatch(requested_node):
            raise ValueError("invalid login")
        certificate = node_certificate(client_socket, requested_node)
        node_id = requested_node
        persistent = auth.get("persistent") in (True, 1)
        username = auth.get("username")
        credentials.verify_executable(auth.get("exe_hash"))
        accounts.verify_device(node_id, username, auth.get("license_id"), certificate)
        token = auth.get("token", "")
        if token:
            accounts.resume(token, username, node_id, certificate)
        else:
            encoded = auth.get("password_hex")
            if not isinstance(encoded, str) or not re.fullmatch(r"(?:[0-9a-f]{2}){1,256}", encoded):
                raise ValueError("invalid login")
            accounts.verify(username, bytes.fromhex(encoded), "node")
        auth.clear()
        if not registry.claim(node_id):
            raise ProtocolError("previous node connection is still closing", STATUS_CONFLICT)
        claimed = True
        if not token:
            token = accounts.issue(username, node_id, certificate)
        send_frame(client_socket, "AUTH_OK", STATUS_OK, {"token": token})
        signed_in = True
        registry.update(node_id, "-", "authenticated", "online", persistent=persistent)
        record_security_event("LOGIN_OK", node_id, detail="node certificate and account accepted")

        request = _receive_secure(client_socket)
        if request["action"] == "RESULT":
            # A reconnect may bring a disk-backed result before the first heartbeat.
            action, task_id = store_result(node_id, request, task_state)
            _send_secure(client_socket, action, task_id=task_id)
            record_security_event("RESULT_RECOVERY", node_id, detail=f"{action} {task_id}")
            request = _receive_secure(client_socket)
        if request["action"] == "LOGOUT":
            accounts.revoke(token)
            return
        _heartbeat(client_socket, request, registry, node_id, preview)

        while True:
            assignment = reserve_task(node_id, task_state)
            if assignment is None:
                if not persistent:
                    raise ProtocolError("no task can accept this node", STATUS_CONFLICT)
                registry.update(node_id, "-", "authenticated", "waiting")
                _send_secure(client_socket, "WAIT", retry_after=1, all_complete=task_state.completed)
                request = _receive_secure(client_socket)
                if request["action"] == "LOGOUT":
                    accounts.revoke(token)
                    record_security_event("LOGOUT", node_id)
                    break
                accounts.resume(token, username, node_id, certificate)
                _heartbeat(client_socket, request, registry, node_id, preview)
                continue

            reserved_task, operation, lower, upper = assignment
            signature = sign_task(f"{reserved_task}|{operation}|{lower}|{upper}")
            registry.update(node_id, "-", "authenticated", "computing")
            _send_secure(client_socket, "TASK", task_id=reserved_task, operation=operation,
                         start=lower, end=upper, signature=signature)
            request = _receive_secure(client_socket)
            if request["action"] == "LOGOUT":
                accounts.revoke(token)
                break
            if request["action"] != "RESULT":
                raise ProtocolError("expected RESULT")
            action, task_id = store_result(node_id, request, task_state, reserved_task)
            _send_secure(client_socket, action, task_id=task_id)
            record_security_event("RESULT_" + action, node_id, detail=task_id)
            if not persistent:
                accounts.revoke(token)
                break
    except (ValueError, ProtocolError) as error:
        detail = str(error) if isinstance(error, ProtocolError) else "credentials or session rejected"
        status = getattr(error, "status", STATUS_UNAUTHORIZED)
        record_security_event("REQUEST_REJECTED" if signed_in else "LOGIN_REJECTED", node_id, detail=detail)
        try:
            if signed_in:
                _send_secure(client_socket, "ERROR", status, detail=detail)
            else:
                send_error(client_socket, status, detail)
        except OSError:
            pass
    except (OSError, socket.timeout):
        record_security_event("CONNECTION_ENDED", node_id, detail="network interruption or timeout")
    except Exception as error:
        record_security_event("SERVER_ERROR", node_id, detail=type(error).__name__)
        print(f"Client processing failed: {type(error).__name__}", flush=True)
    finally:
        if reserved_task is not None:
            release_task(node_id, task_state, reserved_task)
        if claimed:
            preview.offer(node_id, False)
            registry.update(node_id, "-", "signed_out", "offline")
            registry.release(node_id)
