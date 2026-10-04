"""把每轮表决结果保存为简单的 JSON 行记录。"""

import json
from datetime import datetime
from pathlib import Path

from config import (
    REQUIRED_NODES,
    TASK_END,
    TASK_OPERATION,
    TASK_START,
    TOTAL_ROUNDS,
)


AUDIT_FILE = Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"


def save_round(task_state, trusted_value):
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "round": task_state.round_number,
        "task_id": task_state.get_task_id(),
        "operation": TASK_OPERATION,
        "total_range": [TASK_START, TASK_END],
        "subtask_count": TOTAL_ROUNDS,
        "nodes_per_subtask": REQUIRED_NODES,
        "results": task_state.task_results,
        "proofs": task_state.result_proofs,
        "trusted_value": trusted_value,
        "integrated_result": task_state.integrated_result,
        "reputation": task_state.reputation_scores,
        "malicious_nodes": sorted(task_state.malicious_nodes),
        "important_task_nodes": task_state.important_task_nodes,
        "evaluation": task_state.evaluation_report,
    }

    AUDIT_FILE.parent.mkdir(exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as audit_file:
        json.dump(record, audit_file, ensure_ascii=False)
        audit_file.write("\n")


def read_rounds():
    if not AUDIT_FILE.exists():
        return []

    records = []
    with AUDIT_FILE.open("r", encoding="utf-8") as audit_file:
        for line in audit_file:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return records
