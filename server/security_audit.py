"""安全事件使用独立 JSONL 文件保存，便于界面和测试读取。"""

import json
import threading
from datetime import datetime
from config import DATA_DIR


AUDIT_FILE = DATA_DIR / "security_audit.jsonl"
_write_lock = threading.Lock()


# 单独记录登录、拒绝和异常等安全事件，加锁避免并发写入相互干扰。
def record_security_event(event, node_id="-", address="-", detail=""):
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "node_id": node_id,
        "address": "local" if address == "local" else "-",
        "detail": detail,
    }
    AUDIT_FILE.parent.mkdir(exist_ok=True)
    with _write_lock:
        with AUDIT_FILE.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_security_events():
    if not AUDIT_FILE.exists():
        return []
    records = []
    with AUDIT_FILE.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
