"""Receive durable result receipts and finish rounds with strict-majority voting."""

from collections import Counter
import json
import re

from config import CORRECT_REWARD, INITIAL_REPUTATION, MALICIOUS_WRONG_ROUNDS, WRONG_PENALTY
from evaluation import create_evaluation_report
from merkle import verify_result_proof
from operations import merge_values
from protocol import ProtocolError, STATUS_CONFLICT, STATUS_FORBIDDEN, STATUS_UNPROCESSABLE
from scheduler import choose_important_task_nodes


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


def store_result(node_id, payload, state, assigned_task=None):
    """Store a new submission or return the original receipt for an identical retry."""
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

    # Commit the result, round audit and checkpoint together before acknowledging it.
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
            messages.extend(_finish_round(state, db, operation))
            messages.append(f"Audit saved: {task_id}")
    # The console consumes these lines as completed events, so emit them after commit.
    for message in messages:
        print(message, flush=True)
    return "ACCEPTED", task_id


def _finish_round(state, db, operation):
    """Update the audit and advance to the next round inside the receipt transaction."""
    trusted = choose_majority(state.task_results)
    if trusted is None:
        state.failed = state.completed = True
        state.save_round(db, None)
        return ["Vote failed: no strict majority value. Batch stopped."]

    old_scores = state.reputation_scores.copy()
    old_malicious = state.malicious_nodes.copy()
    state.trusted_results.append(trusted)
    state.integrated_result = merge_values(operation, state.trusted_results)
    update_reputation(state.task_results, trusted, state)
    messages = [f"Majority result: {trusted}", f"Integrated result: {state.integrated_result}"]
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
    return messages
