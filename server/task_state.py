"""Durable batches, offered assignments, result receipts and round audit records."""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import threading
import uuid

from config import (
    DATA_DIR, MAX_CONCURRENT_CLIENTS, REQUIRED_NODES, TASK_ENABLED, TASK_END, TASK_ID_PREFIX,
    TASK_OPERATION, TASK_START, TOTAL_ROUNDS,
)
from operations import expected_result, is_supported

DATABASE = DATA_DIR / "tasks.sqlite3"


def default_settings():
    return {
        "operation": TASK_OPERATION, "start": TASK_START, "end": TASK_END,
        "subtask_count": TOTAL_ROUNDS, "nodes_per_subtask": REQUIRED_NODES,
        "important": False,
    }


def validate_settings(settings):
    start, end = settings["start"], settings["end"]
    rounds, nodes = settings["subtask_count"], settings["nodes_per_subtask"]
    if any(type(value) is not int for value in (start, end, rounds, nodes)):
        raise ValueError("task bounds, rounds and node count must be integers")
    if not is_supported(settings["operation"]) or not 1 <= rounds <= 500:
        raise ValueError("unknown operation or invalid round count")
    if not 3 <= nodes <= MAX_CONCURRENT_CLIENTS or not rounds * 4 <= end - start + 1 <= 2_000_000:
        raise ValueError("node count exceeds service capacity, or fewer than four values per subtask")
    if not -2_147_483_647 <= start <= end <= 2_147_483_646:
        raise ValueError("task bounds exceed the client range")
    if settings["operation"] == "SUM_RANGE":
        # No partial sum can exceed the side of the interval with the most magnitude.
        totals = (expected_result("SUM_RANGE", start, min(end, -1)) if start < 0 else 0,
                  expected_result("SUM_RANGE", max(start, 1), end) if end > 0 else 0)
        if min(totals) < -2_147_483_647 or max(totals) > 2_147_483_646:
            raise ValueError("a partial sum exceeds the client range")


def connect():
    return sqlite3.connect(DATABASE, timeout=5)


class TaskState:
    def __init__(self):
        self.lock = threading.RLock()
        self.assigned_nodes = set()
        DATABASE.parent.mkdir(parents=True, exist_ok=True)
        with closing(connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS checkpoint (id INTEGER PRIMARY KEY, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS results (
                    task_id TEXT NOT NULL, node_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (task_id, node_id)
                );
                CREATE TABLE IF NOT EXISTS rounds (
                    task_id TEXT PRIMARY KEY, audit TEXT NOT NULL
                );
            """)
            recovered = db.execute("SELECT state FROM checkpoint WHERE id = 1").fetchone()
        if recovered:
            self.restore(recovered[0])
        else:
            self.reputation_scores = {}
            self.wrong_rounds = {}
            self.malicious_nodes = set()
            self.important_task_nodes = []
            self.reset_batch(default_settings(), uuid.uuid4().hex, completed=not TASK_ENABLED)
            with self.transaction():
                pass

    def reset_batch(self, settings, batch_id, completed=False):
        validate_settings(settings)
        self.settings = dict(settings)
        self.session_id = batch_id
        self.round_number = 1
        self.task_results = {}
        self.result_proofs = {}
        self.offered_nodes = set()
        self.assigned_nodes.clear()
        self.evaluation_report = {}
        self.trusted_results = []
        self.integrated_result = 0
        self.completed = completed
        self.failed = False

    def get_task_id(self):
        return f"{TASK_ID_PREFIX}-{self.session_id}-{self.round_number:03d}"

    def start_next_round(self):
        self.round_number += 1
        self.task_results = {}
        self.result_proofs = {}
        self.offered_nodes.clear()
        self.assigned_nodes.clear()

    def checkpoint(self):
        fields = {key: value for key, value in vars(self).items() if key not in ("lock", "assigned_nodes")}
        for name in ("offered_nodes", "malicious_nodes"):
            fields[name] = sorted(fields[name])
        return json.dumps(fields, separators=(",", ":"))

    def restore(self, checkpoint):
        fields = json.loads(checkpoint)
        for name in ("offered_nodes", "malicious_nodes"):
            fields[name] = set(fields[name])
        vars(self).update(fields)

    @contextmanager
    def transaction(self):
        # The lock remains held until both the receipt and checkpoint are durable.
        with self.lock:
            previous = self.checkpoint()
            assigned = self.assigned_nodes.copy()
            try:
                with closing(connect()) as db, db:
                    yield db
                    db.execute("REPLACE INTO checkpoint VALUES (1, ?)", (self.checkpoint(),))
            except BaseException:
                self.restore(previous)
                self.assigned_nodes = assigned
                raise

    def start_batch(self, settings, request_id):
        with self.lock:
            if request_id == self.session_id:
                return
            if not self.completed:
                raise ValueError("a task batch is already running")
            with self.transaction():
                self.reset_batch(settings, request_id)

    def save_round(self, db, trusted):
        record = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "round": self.round_number, "task_id": self.get_task_id(),
            "operation": self.settings["operation"],
            "total_range": [self.settings["start"], self.settings["end"]],
            "subtask_count": self.settings["subtask_count"],
            "nodes_per_subtask": self.settings["nodes_per_subtask"],
            "results": self.task_results, "proofs": self.result_proofs,
            "trusted_value": trusted, "integrated_result": self.integrated_result,
            "reputation": self.reputation_scores,
            "malicious_nodes": sorted(self.malicious_nodes),
            "important_task_nodes": self.important_task_nodes,
            "evaluation": self.evaluation_report,
        }
        db.execute("INSERT INTO rounds VALUES (?, ?)", (self.get_task_id(), json.dumps(record)))
