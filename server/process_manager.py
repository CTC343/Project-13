"""控制服务端进程和用户手动打开的客户端窗口。"""

import os
import subprocess
import sys
import threading
from pathlib import Path

from config import (
    REQUIRED_NODES,
    TASK_END,
    TASK_OPERATION,
    TASK_START,
    TOTAL_ROUNDS,
)
CREATE_NO_WINDOW = 0x08000000


class ProcessManager:
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.project_root = Path(__file__).resolve().parent.parent
        self.server_process = None
        self.server_ready = threading.Event()

    def default_task_settings(self):
        return {
            "operation": TASK_OPERATION,
            "start": TASK_START,
            "end": TASK_END,
            "subtask_count": TOTAL_ROUNDS,
            "nodes_per_subtask": REQUIRED_NODES,
        }

    def start_server(self, task_settings=None):
        if self.is_server_running():
            self.event_queue.put(("status", "服务端已经在运行"))
            return False

        server_file = self.project_root / "server" / "server.py"
        settings = task_settings or self.default_task_settings()
        task_enabled = task_settings is not None
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PROJECT13_OPERATION"] = settings["operation"]
        environment["PROJECT13_TASK_ENABLED"] = "1" if task_enabled else "0"
        environment["PROJECT13_TASK_START"] = str(settings["start"])
        environment["PROJECT13_TASK_END"] = str(settings["end"])
        environment["PROJECT13_SUBTASK_COUNT"] = str(
            settings["subtask_count"]
        )
        environment["PROJECT13_REQUIRED_NODES"] = str(
            settings["nodes_per_subtask"]
        )
        self.server_ready.clear()

        self.server_process = subprocess.Popen(
            [sys.executable, "-u", str(server_file)],
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            creationflags=CREATE_NO_WINDOW,
        )

        reader = threading.Thread(target=self._read_server_output, daemon=True)
        reader.start()
        self.event_queue.put(("status", "服务端正在启动"))
        return True

    def stop_server(self):
        if not self.is_server_running():
            self.server_process = None
            self.event_queue.put(("status", "服务端未运行"))
            return

        self.server_process.terminate()
        try:
            self.server_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.server_process.kill()
            self.server_process.wait(timeout=2)

        self.server_process = None
        self.server_ready.clear()
        self.event_queue.put(("status", "服务端已停止"))

    def restart_server(self, task_settings):
        settings = task_settings or self.default_task_settings()
        self.stop_server()
        self.start_server(settings)

    def open_client_window(self):
        client_file = self.project_root / "client" / "client_gui.exe"
        if not client_file.exists():
            self.event_queue.put(("status", "请先编译 client_gui.exe"))
            return

        subprocess.Popen([str(client_file)], cwd=self.project_root)
        self.event_queue.put(("status", "客户端窗口已打开"))

    def is_server_running(self):
        return (
            self.server_process is not None
            and self.server_process.poll() is None
        )

    def _read_server_output(self):
        process = self.server_process
        if process is None or process.stdout is None:
            return

        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if line.startswith("READY:"):
                self.server_ready.set()
                self.event_queue.put(("status", "服务端运行中"))
            self.event_queue.put(("server_line", line))

        self.event_queue.put(("server_stopped", "服务端进程已结束"))
