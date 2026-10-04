"""认证后的节点任务分发、结果校验、表决和信誉更新。"""

import socket
import time

from audit import save_round
from config import (
    CORRECT_REWARD,
    INITIAL_REPUTATION,
    MALICIOUS_WRONG_ROUNDS,
    REQUIRED_NODES,
    TASK_OPERATION,
    TOTAL_ROUNDS,
    WRONG_PENALTY,
)
from evaluation import create_evaluation_report, save_evaluation_report
from merkle import verify_result_proof
from operations import merge_values
from protocol import (
    ProtocolError,
    STATUS_CONFLICT,
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNAUTHORIZED,
    STATUS_UNPROCESSABLE,
    receive_frame,
    send_error,
    send_frame,
)
from scheduler import choose_important_task_nodes
from secure_channel import SecureSession
from security_audit import record_security_event
from signature import sign_task
from task_planner import get_subtask_range


def choose_majority(task_results):
    result_counts = {}
    required_votes = len(task_results) // 2 + 1
    for result_value in task_results.values():
        result_counts[result_value] = result_counts.get(result_value, 0) + 1
    for result_value, vote_count in result_counts.items():
        if vote_count >= required_votes:
            return result_value
    return None


def update_reputation(task_results, trusted_value, task_state):
    for node_id, result_value in task_results.items():
        old_score = task_state.reputation_scores.get(node_id, INITIAL_REPUTATION)
        if result_value == trusted_value:
            new_score = min(100, old_score + CORRECT_REWARD)
        else:
            new_score = max(0, old_score - WRONG_PENALTY)
            wrong_count = task_state.wrong_rounds.get(node_id, 0) + 1
            task_state.wrong_rounds[node_id] = wrong_count
            print(f"Wrong rounds: {node_id} -> {wrong_count}", flush=True)
            if wrong_count == MALICIOUS_WRONG_ROUNDS:
                task_state.malicious_nodes.add(node_id)
                print(f"Malicious node detected: {node_id}", flush=True)
        task_state.reputation_scores[node_id] = new_score
        print(f"Reputation: {node_id} {old_score} -> {new_score}", flush=True)


def finish_task(task_state):
    task_results = task_state.task_results
    print(f"Redundant results complete: {len(task_results)} nodes", flush=True)
    for node_id, result_value in task_results.items():
        print(f"  {node_id}: {result_value}", flush=True)

    trusted_value = choose_majority(task_results)
    if trusted_value is None:
        print("Vote failed: no strict majority value.", flush=True)
        save_round(task_state, None)
        return False

    print(f"Majority result: {trusted_value}", flush=True)
    task_state.trusted_results.append(trusted_value)
    task_state.integrated_result = merge_values(
        TASK_OPERATION, task_state.trusted_results
    )
    print(f"Integrated result: {task_state.integrated_result}", flush=True)
    update_reputation(task_results, trusted_value, task_state)

    task_state.important_task_nodes = choose_important_task_nodes(
        task_state.reputation_scores, task_state.malicious_nodes
    )
    excluded_nodes = sorted(
        node_id for node_id in task_results
        if node_id not in task_state.important_task_nodes
    )
    print(
        "Important-task eligible: "
        + ", ".join(task_state.important_task_nodes), flush=True
    )
    print("Important-task excluded: " + ", ".join(excluded_nodes), flush=True)

    if task_state.round_number == TOTAL_ROUNDS:
        task_state.evaluation_report = create_evaluation_report(
            task_state, task_state.integrated_result
        )
        save_evaluation_report(task_state.evaluation_report)
        report = task_state.evaluation_report
        print(
            "Evaluation accuracy error: "
            f"{report['accuracy_error_percent']:.2f}% "
            f"{'PASS' if report['accuracy_passed'] else 'FAIL'}", flush=True
        )
        print(
            "Evaluation security overhead: "
            f"{report['security_overhead_percent']:.2f}% "
            f"{'PASS' if report['security_overhead_passed'] else 'FAIL'}",
            flush=True,
        )
        print(
            "Evaluation malicious ratio: "
            f"{report['malicious_ratio_percent']:.2f}% "
            f"{'PASS' if report['malicious_detection_passed'] else 'FAIL'}",
            flush=True,
        )

    save_round(task_state, trusted_value)
    print(f"Audit saved: round {task_state.round_number}", flush=True)
    return True


def _send_secure(client_socket, session, action, status=STATUS_OK, **values):
    payload = {"action": action}
    payload.update(values)
    send_frame(
        client_socket, "SECURE", status,
        session.protect_server_message(payload)
    )


def _receive_secure(client_socket, session, expected_action):
    payload = _receive_secure_any(client_socket, session)
    if payload.get("action") != expected_action:
        raise ProtocolError(f"expected {expected_action}")
    return payload


def _receive_secure_any(client_socket, session):
    message_type, _, envelope = receive_frame(client_socket)
    if message_type != "SECURE":
        raise ProtocolError("expected secure message")
    try:
        payload = session.open_client_message(envelope)
    except ValueError as error:
        raise ProtocolError(str(error), STATUS_UNAUTHORIZED) from None
    return payload


def _try_reserve_task(node_id, last_round, task_state):
    with task_state.lock:
        if task_state.completed:
            return None
        if task_state.round_number <= last_round:
            return None
        if node_id in task_state.assigned_nodes:
            return None
        if len(task_state.assigned_nodes) >= REQUIRED_NODES:
            return None

        task_id = task_state.get_task_id()
        task_start, task_end = get_subtask_range(task_state.round_number)
        task_state.assigned_nodes.add(node_id)
        return task_id, task_start, task_end, task_state.round_number


def _store_result(node_id, payload, task_info, task_state):
    task_id, _, _, _ = task_info
    if payload.get("task_id") != task_id or payload.get("node_id") != node_id:
        raise ProtocolError("task or node identity does not match", STATUS_FORBIDDEN)
    try:
        result_value = int(payload["value"])
        merkle_root = payload["merkle_root"]
        proof_steps = payload["proof_steps"]
    except (KeyError, TypeError, ValueError):
        raise ProtocolError("invalid result body", STATUS_UNPROCESSABLE) from None

    if not verify_result_proof(
        TASK_OPERATION, result_value, proof_steps, merkle_root
    ):
        raise ProtocolError("invalid Merkle proof", STATUS_UNPROCESSABLE)

    with task_state.lock:
        if task_id != task_state.get_task_id():
            raise ProtocolError("subtask is no longer active", STATUS_CONFLICT)
        if node_id in task_state.task_results:
            raise ProtocolError("duplicate result", STATUS_CONFLICT)

        task_state.task_results[node_id] = result_value
        task_state.result_proofs[node_id] = {
            "root": merkle_root, "steps": proof_steps
        }
        result_number = len(task_state.task_results)
        print(
            f"Result {result_number}/{REQUIRED_NODES}: "
            f"{node_id} -> {result_value}", flush=True
        )
        print(f"Merkle proof verified: {node_id}", flush=True)

        if result_number == REQUIRED_NODES:
            finish_task(task_state)
            print(f"Round {task_state.round_number} complete.", flush=True)
            if task_state.round_number == TOTAL_ROUNDS:
                task_state.completed = True
                print("All subtask rounds complete.", flush=True)
            else:
                task_state.start_next_round()
                print(f"Next task: {task_state.get_task_id()}", flush=True)
        return result_value


def handle_client(client_socket, client_address, task_state,
                  credential_store, node_registry):
    address_text = f"{client_address[0]}:{client_address[1]}"
    node_id = "-"
    task_info = None
    session = None
    result_stored = False
    persistent = False
    last_round = 0
    client_socket.settimeout(8)

    try:
        message_type, _, auth_request = receive_frame(client_socket)
        if message_type != "AUTH":
            raise ProtocolError("AUTH must be the first message", STATUS_UNAUTHORIZED)
        node_id = auth_request.get("node_id", "-")
        persistent = bool(auth_request.get("persistent", False))
        auth_key = credential_store.authenticate(auth_request)
        session_id, server_nonce, server_proof, session_key = (
            credential_store.create_session(auth_key, auth_request["client_nonce"])
        )
        send_frame(client_socket, "AUTH_OK", STATUS_OK, {
            "session_id": session_id,
            "server_nonce": server_nonce,
            "server_proof": server_proof,
            "license_status": "valid",
            "integrity_status": "valid",
        })
        session = SecureSession(session_id, session_key)
        node_registry.update(node_id, address_text, "authenticated", "online")
        record_security_event("LOGIN_OK", node_id, address_text, "license and executable verified")

        heartbeat = _receive_secure(client_socket, session, "HEARTBEAT")
        if int(heartbeat.get("sent_at", 0)) <= 0:
            raise ProtocolError("invalid heartbeat")
        node_registry.update(node_id, address_text, "authenticated", "heartbeat")
        _send_secure(client_socket, session, "HEARTBEAT_ACK", server_time=int(time.time()))

        while True:
            task_info = _try_reserve_task(node_id, last_round, task_state)
            if task_info is None:
                if not persistent:
                    raise ProtocolError(
                        "current subtask cannot accept this node",
                        STATUS_CONFLICT,
                    )

                node_registry.update(
                    node_id, address_text, "authenticated", "waiting"
                )
                with task_state.lock:
                    all_complete = task_state.completed
                _send_secure(
                    client_socket, session, "WAIT",
                    retry_after=2, all_complete=all_complete
                )
                control = _receive_secure_any(client_socket, session)
                action = control.get("action")
                if action == "LOGOUT":
                    record_security_event(
                        "LOGOUT", node_id, address_text, "client requested"
                    )
                    break
                if action != "HEARTBEAT" or int(control.get("sent_at", 0)) <= 0:
                    raise ProtocolError("expected HEARTBEAT or LOGOUT")
                node_registry.update(
                    node_id, address_text, "authenticated", "heartbeat"
                )
                _send_secure(
                    client_socket, session, "HEARTBEAT_ACK",
                    server_time=int(time.time())
                )
                node_registry.update(
                    node_id, address_text, "authenticated", "waiting"
                )
                continue

            task_id, task_start, task_end, assigned_round = task_info
            result_stored = False
            task_text = f"{task_id}|{TASK_OPERATION}|{task_start}|{task_end}"
            task_signature = sign_task(task_text)
            node_registry.update(
                node_id, address_text, "authenticated", "computing"
            )
            _send_secure(
                client_socket, session, "TASK", task_id=task_id,
                operation=TASK_OPERATION, start=task_start, end=task_end,
                signature=task_signature
            )

            result_payload = _receive_secure(client_socket, session, "RESULT")
            _store_result(node_id, result_payload, task_info, task_state)
            result_stored = True
            last_round = assigned_round
            _send_secure(client_socket, session, "ACCEPTED", task_id=task_id)
            node_registry.update(
                node_id, address_text, "authenticated",
                "waiting" if persistent else "completed"
            )
            record_security_event(
                "RESULT_ACCEPTED", node_id, address_text, task_id
            )
            if not persistent:
                break
            task_info = None

    except ValueError as error:
        record_security_event("LOGIN_REJECTED", node_id, address_text, str(error))
        node_registry.update(node_id, address_text, "rejected", "offline")
        try:
            send_error(client_socket, STATUS_UNAUTHORIZED, str(error))
        except OSError:
            pass
    except (ProtocolError, socket.timeout) as error:
        detail = str(error) or "socket timeout"
        status = getattr(error, "status", STATUS_UNPROCESSABLE)
        record_security_event("REQUEST_REJECTED", node_id, address_text, detail)
        try:
            if session is None:
                send_error(client_socket, status, detail)
            else:
                _send_secure(client_socket, session, "ERROR", status, detail=detail)
        except OSError:
            pass
    except (OSError, UnicodeDecodeError) as error:
        record_security_event("NETWORK_ERROR", node_id, address_text, str(error))
        print(f"Client error: {address_text} {error}", flush=True)
    except Exception as error:
        record_security_event("SERVER_ERROR", node_id, address_text, str(error))
        print(f"Unexpected client error: {address_text} {error}", flush=True)
        try:
            if session is None:
                send_error(client_socket, 500, "internal server error")
            else:
                _send_secure(
                    client_socket, session, "ERROR", 500,
                    detail="internal server error"
                )
        except OSError:
            pass
    finally:
        if task_info is not None and not result_stored:
            with task_state.lock:
                task_state.assigned_nodes.discard(node_id)
        if node_id != "-":
            node_registry.update(node_id, address_text, "signed_out", "offline")
