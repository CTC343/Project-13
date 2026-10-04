"""安全事件使用独立 JSONL 文件保存，便于界面和测试读取。"""

import json
import threading
from datetime import datetime
from pathlib import Path


AUDIT_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "security_audit.jsonl"
)
_write_lock = threading.Lock()


def record_security_event(event, node_id="-", address="-", detail=""):
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "node_id": node_id,
        "address": address,
        "detail": detail,
    }
    AUDIT_FILE.parent.mkdir(exist_ok=True)
    with _write_lock:
        with AUDIT_FILE.open("a", encoding="utf-8") as output:
            json.dump(record, output, ensure_ascii=False)
            output.write("\n")


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
