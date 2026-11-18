"""Report accuracy and detection from the committed final round."""

from contextlib import closing
import json

from operations import expected_result
from task_state import DATABASE, connect


def create_evaluation_report(task_state, trusted_value):
    settings = task_state.settings
    operation = settings["operation"]
    answer = expected_result(operation, settings["start"], settings["end"])
    difference = abs(trusted_value - answer)
    error = difference / abs(answer) * 100 if answer else float(difference)
    participating = set(task_state.task_results)
    detected = task_state.malicious_nodes & participating
    ratio = len(detected) / settings["nodes_per_subtask"] * 100
    return {
        "operation": operation,
        "accuracy_error_percent": round(error, 4),
        "accuracy_passed": error < 1,
        "security_overhead_percent": None,
        "security_overhead_passed": None,
        "malicious_ratio_percent": round(ratio, 2),
        "malicious_detection_passed": 0 < ratio <= 10 and task_state.round_number <= 5,
        "detected_nodes": sorted(detected),
    }


def read_evaluation_report():
    if not DATABASE.exists():
        return {}
    with closing(connect()) as db:
        latest = db.execute("SELECT state FROM checkpoint WHERE id=1").fetchone()
    return json.loads(latest[0])["evaluation_report"] if latest else {}
