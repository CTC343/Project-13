"""保存节点登录、心跳和任务状态，供日志、审计和界面展示。"""

import threading
from datetime import datetime


class NodeRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._nodes = {}

    def update(self, node_id, address, login_status, state, persistent=None):
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            node = self._nodes.setdefault(node_id, {})
            node.update({
                "address": address,
                "login_status": login_status,
                "state": state,
                "last_seen": now,
            })
            if persistent is not None:
                node["persistent"] = bool(persistent)
            node.setdefault("persistent", False)
            if state == "heartbeat":
                node["last_heartbeat"] = now
            node.setdefault("last_heartbeat", "-")
            snapshot = dict(node)
            print(
                "NODE_STATUS "
                f"{node_id} login={snapshot['login_status']} "
                f"state={snapshot['state']} "
                f"heartbeat={snapshot['last_heartbeat']} "
                f"address={snapshot['address']} "
                f"persistent={int(snapshot['persistent'])}",
                flush=True,
            )

    def snapshot(self):
        with self._lock:
            return {key: dict(value) for key, value in self._nodes.items()}
