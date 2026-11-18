"""Authenticated task distribution and result recovery over TLS."""

from collections import Counter
import json
import re
import socket
import time

from accounts import ACCOUNT_ID
from config import (
    CORRECT_REWARD, IMPORTANT_TASK_MIN_REPUTATION, INITIAL_REPUTATION,
    MALICIOUS_WRONG_ROUNDS, SOCKET_TIMEOUT_SECONDS, WRONG_PENALTY,
)
from evaluation import create_evaluation_report
from merkle import verify_result_proof
from operations import merge_values
from protocol import (
    ProtocolError, STATUS_CONFLICT, STATUS_FORBIDDEN, STATUS_OK,
    STATUS_UNAUTHORIZED, STATUS_UNPROCESSABLE, receive_frame, send_error, send_frame,
)
from scheduler import choose_important_task_nodes
from security_audit import record_security_event
from signature import sign_task
from task_planner import get_subtask_range
from tls_transport import node_certificate


def choose_majority(task_results):
    counts = Counter(task_results.values())
    return next((value for value, count in counts.items() if count > len(task_results) // 2), None)


def update_reputation(task_results, trusted_value, task_state):
    for node, value in task_results.items():
        score = task_state.reputation_scores.get(node, INITIAL_REPUTATION)
        if value == trusted_value:
            task_state.reputation_scores[node] = min(100, score + CORRECT_REWARD)
            task_state.wrong_rounds[node] = 0
        else:
            task_state.reputation_scores[node] = max(0, score - WRONG_PENALTY)
            count = task_state.wrong_rounds.get(node, 0) + 1
            task_state.wrong_rounds[node] = count
            if count >= MALICIOUS_WRONG_ROUNDS:
                task_state.malicious_nodes.add(node)
    task_state.important_task_nodes = choose_important_task_nodes(
        task_state.reputation_scores, task_state.malicious_nodes,
    )


def _send_secure(client_socket, action, status=STATUS_OK, **values):
    send_frame(client_socket, "SECURE", status, {"action": action, **values})


def _receive_secure(client_socket):
    message_type, status, payload = receive_frame(client_socket)
    if message_type != "SECURE" or status != 0 or not isinstance(payload.get("action"), str):
        raise ProtocolError("invalid business frame")
    return payload


def _try_reserve_task(node_id, state):
    with state.lock:
        required = state.settings["nodes_per_subtask"]
        if (state.completed or node_id in state.task_results or node_id in state.assigned_nodes
                or len(state.assigned_nodes) + len(state.task_results) >= required):
            return None
        if state.settings["important"] and (
            node_id in state.malicious_nodes or
            state.reputation_scores.get(node_id, INITIAL_REPUTATION) < IMPORTANT_TASK_MIN_REPUTATION
        ):
            return None
        if node_id not in state.offered_nodes:
            with state.transaction():
                state.offered_nodes.add(node_id)
        state.assigned_nodes.add(node_id)
        lower, upper = get_subtask_range(
            state.round_number, state.settings["start"], state.settings["end"],
            state.settings["subtask_count"],
        )
        return state.get_task_id(), state.settings["operation"], lower, upper


def _store_result(node_id, payload, state, assigned_task=None):
    task_id, value = payload.get("task_id"), payload.get("value")
    root, steps = payload.get("merkle_root"), payload.get("proof_steps")
    if not isinstance(task_id, str) or not re.fullmatch(r"task-[0-9a-f]{32}-[0-9]{3}", task_id):
        raise ProtocolError("invalid task identity", STATUS_UNPROCESSABLE)
    if payload.get("node_id") != node_id or (assigned_task is not None and assigned_task != task_id):
        raise ProtocolError("task or node identity does not match", STATUS_FORBIDDEN)
    if (type(value) is not int or not -(2**31) <= value < 2**31 or
            not isinstance(root, str) or not re.fullmatch(r"[0-9a-f]{64}", root) or
            not isinstance(steps, str) or not re.fullmatch(r"-?\d{1,10}(,-?\d{1,10}){3}", steps)):
        raise ProtocolError("invalid result format", STATUS_UNPROCESSABLE)
    encoded = json.dumps({"value": value, "root": root, "steps": steps}, separators=(",", ":"))
    messages = []

    with state.transaction() as db:
        previous = db.execute(
            "SELECT payload FROM results WHERE task_id = ? AND node_id = ?", (task_id, node_id)
        ).fetchone()
        if previous is not None:
            if previous[0] != encoded:
                raise ProtocolError("result differs from the durable receipt", STATUS_CONFLICT)
            return "ACCEPTED", task_id
        if state.completed or task_id != state.get_task_id() or node_id not in state.offered_nodes:
            return "RETAIN", task_id
        operation = state.settings["operation"]
        if not verify_result_proof(operation, value, steps, root):
            raise ProtocolError("invalid Merkle proof", STATUS_UNPROCESSABLE)
        db.execute("INSERT INTO results VALUES (?, ?, ?)", (task_id, node_id, encoded))
        state.task_results[node_id] = value
        state.result_proofs[node_id] = {"root": root, "steps": steps}
        state.assigned_nodes.discard(node_id)
        required = state.settings["nodes_per_subtask"]
        messages.append(f"Result {len(state.task_results)}/{required}: {node_id} -> {value}")

        if len(state.task_results) == required:
            trusted = choose_majority(state.task_results)
            if trusted is None:
                state.failed = state.completed = True
                state.save_round(db, None)
                messages.append("Vote failed: no strict majority value. Batch stopped.")
            else:
                old_scores = state.reputation_scores.copy()
                old_malicious = state.malicious_nodes.copy()
                state.trusted_results.append(trusted)
                state.integrated_result = merge_values(operation, state.trusted_results)
                update_reputation(state.task_results, trusted, state)
                messages.extend((f"Majority result: {trusted}", f"Integrated result: {state.integrated_result}"))
                for node in state.task_results:
                    old = old_scores.get(node, INITIAL_REPUTATION)
                    messages.append(f"Reputation: {node} {old} -> {state.reputation_scores[node]}")
                for node in sorted(state.malicious_nodes - old_malicious):
                    messages.append(f"Malicious node detected: {node}")
                excluded = sorted(set(state.task_results) - set(state.important_task_nodes))
                messages.append("Important-task excluded: " + ", ".join(excluded))
                if state.round_number == state.settings["subtask_count"]:
                    state.completed = True
                    state.evaluation_report = create_evaluation_report(state, state.integrated_result)
                state.save_round(db, trusted)
                messages.append(f"Round {state.round_number} complete.")
                if state.completed:
                    messages.append("All subtask rounds complete.")
                else:
                    state.start_next_round()
            messages.append(f"Audit saved: {task_id}")
    for message in messages:
        print(message, flush=True)
    return "ACCEPTED", task_id


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
            action, task_id = _store_result(node_id, request, task_state)
            _send_secure(client_socket, action, task_id=task_id)
            record_security_event("RESULT_RECOVERY", node_id, detail=f"{action} {task_id}")
            request = _receive_secure(client_socket)
        if request["action"] == "LOGOUT":
            accounts.revoke(token)
            return
        _heartbeat(client_socket, request, registry, node_id, preview)

        while True:
            assignment = _try_reserve_task(node_id, task_state)
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
            action, task_id = _store_result(node_id, request, task_state, reserved_task)
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
            with task_state.lock:
                if reserved_task == task_state.get_task_id():
                    task_state.assigned_nodes.discard(node_id)
        if claimed:
            preview.offer(node_id, False)
            registry.update(node_id, "-", "signed_out", "offline")
            registry.release(node_id)
