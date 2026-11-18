"""为当前轮次分配节点，并按信誉限制重要任务。"""

from config import IMPORTANT_TASK_MIN_REPUTATION, INITIAL_REPUTATION
from task_planner import get_subtask_range


def _eligible_for_important_task(node_id, score, malicious_nodes):
    return score >= IMPORTANT_TASK_MIN_REPUTATION and node_id not in malicious_nodes


def choose_important_task_nodes(reputation_scores, malicious_nodes):
    return sorted(
        node for node, score in reputation_scores.items()
        if _eligible_for_important_task(node, score, malicious_nodes)
    )


def reserve_task(node_id, state):
    """Reserve a slot and persist the offer before sending the task."""
    with state.lock:
        required = state.settings["nodes_per_subtask"]
        if (state.completed or node_id in state.task_results or node_id in state.assigned_nodes
                or len(state.assigned_nodes) + len(state.task_results) >= required):
            return None
        if state.settings["important"] and not _eligible_for_important_task(
            node_id, state.reputation_scores.get(node_id, INITIAL_REPUTATION), state.malicious_nodes,
        ):
            return None
        # An offer survives a disconnect so the node can resend a result after restart.
        # The active reservation is local to the current connection.
        if node_id not in state.offered_nodes:
            with state.transaction():
                state.offered_nodes.add(node_id)
        state.assigned_nodes.add(node_id)
        lower, upper = get_subtask_range(
            state.round_number, state.settings["start"], state.settings["end"],
            state.settings["subtask_count"],
        )
        return state.get_task_id(), state.settings["operation"], lower, upper


def release_task(node_id, state, task_id):
    """Release a disconnected node's slot without touching a newer round."""
    with state.lock:
        if task_id == state.get_task_id():
            state.assigned_nodes.discard(node_id)
