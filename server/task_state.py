"""保存当前轮次、结果和节点信誉。"""

import uuid
import threading

from config import TASK_ENABLED, TASK_ID_PREFIX


class TaskState:
    def __init__(self):
        self.lock = threading.RLock()
        self.session_id = uuid.uuid4().hex[:8]
        self.round_number = 1
        self.task_results = {}
        self.result_proofs = {}
        self.reputation_scores = {}
        self.wrong_rounds = {}
        self.malicious_nodes = set()
        self.important_task_nodes = []
        self.evaluation_report = {}
        self.trusted_results = []
        self.integrated_result = 0
        self.completed = not TASK_ENABLED
        self.assigned_nodes = set()

    def get_task_id(self):
        return f"{TASK_ID_PREFIX}-{self.session_id}-{self.round_number:03d}"

    def start_next_round(self):
        self.round_number += 1
        self.task_results = {}
        self.result_proofs = {}
        self.assigned_nodes = set()
