"""Persistent, searchable operation logs. Store only approved fields from server output."""

from collections import deque
from logging import ERROR, INFO, WARNING, Formatter, LogRecord
from logging.handlers import RotatingFileHandler
import re
import threading

from config import DATA_DIR

LOG_PATH = DATA_DIR / "runtime.log"
BACKUPS = 3
LOG_LOCK = threading.Lock()
NODE_STATE = re.compile(r"NODE_STATUS (node-[0-9a-f]{24}) login=(authenticated|signed_out) "
                        r"state=(online|offline)(?: .*)?\Z")
TASK_ID = r"(task-[a-f0-9]{32}-\d{3})"
TASK_EVENT = re.compile(rf"(Batch started|Batch active|Audit saved): {TASK_ID}\Z")
NODE_RESULT = re.compile(r"Result (\d{1,3})/(\d{1,3}): (node-[0-9a-f]{24}) -> (-?\d{1,10})\Z")
INTEGRATED = re.compile(r"Integrated result: (-?\d{1,16})\Z")


class RuntimeLog:
    def __init__(self):
        self._handler = RotatingFileHandler(
            LOG_PATH, maxBytes=2 * 1024 * 1024, backupCount=BACKUPS, encoding="utf-8", delay=True,
        )
        self._handler.setFormatter(Formatter("%(asctime)s\t%(levelname)s\t%(message)s",
                                             datefmt="%Y-%m-%d %H:%M:%S"))

    def write(self, level, message):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = LogRecord("project13.runtime", level, "", 0, message, (), None)
        with LOG_LOCK:
            self._handler.handle(entry)
        return self._handler.format(entry)

    def from_server_line(self, line):
        match = NODE_STATE.fullmatch(line)
        if match:
            node, _, state = match.groups()
            return self.write(INFO, f"{node} {'上线' if state == 'online' else '离线'}")
        match = TASK_EVENT.fullmatch(line)
        if match:
            event, task_id = match.groups()
            captions = {"Batch started": "开始任务批次", "Batch active": "恢复任务批次", "Audit saved": "已保存任务记录"}
            return self.write(INFO, f"{captions[event]} {task_id}")
        match = NODE_RESULT.fullmatch(line)
        if match:
            count, total, node, value = match.groups()
            return self.write(INFO, f"{node} 提交结果 {value}（{count}/{total}）")
        match = INTEGRATED.fullmatch(line)
        if match:
            return self.write(INFO, f"累计整合结果 {match[1]}")
        for prefix, level, message in (
            ("READY:", INFO, "服务器已就绪"),
            ("Batch rejected:", WARNING, "拒绝启动任务，请检查任务配置和服务状态"),
            ("Vote failed:", WARNING, "没有得到严格多数，任务批次停止"),
            ("Client processing failed:", ERROR, "处理客户端请求时出错"),
            ("Server setup failed:", ERROR, "服务端配置或文件访问检查失败"),
            ("All subtask rounds complete.", INFO, "任务批次已完成"),
        ):
            if line.startswith(prefix):
                return self.write(level, message)
        return None


def matches(line, level, query):
    parts = line.split("\t", 2)
    return len(parts) == 3 and (not level or parts[1] == level) and query.casefold() in line.casefold()


def recent_logs(level="", query="", limit=500):
    logs = deque(maxlen=limit)
    rotated = [LOG_PATH.with_name(f"{LOG_PATH.name}.{index}") for index in range(BACKUPS, 0, -1)]
    with LOG_LOCK:
        for path in (*rotated, LOG_PATH):
            try:
                with path.open(encoding="utf-8", errors="replace") as stream:
                    logs.extend(line.rstrip("\r\n") for line in stream if matches(line, level, query))
            except FileNotFoundError:
                continue
    return list(logs)
