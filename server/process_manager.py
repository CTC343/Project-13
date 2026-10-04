"""控制服务端进程、十节点演示和客户端窗口。"""

import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import (
    REQUIRED_NODES,
    TASK_END,
    TASK_OPERATION,
    TASK_START,
    TOTAL_ROUNDS,
)
from operations import operation_label


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
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PROJECT13_OPERATION"] = settings["operation"]
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

    def restart_and_run_demo(self, task_settings=None):
        settings = task_settings or self.default_task_settings()
        self.stop_server()
        self.start_server(settings)

        worker = threading.Thread(
            target=self._run_demo,
            args=(settings,),
            daemon=True,
        )
        worker.start()

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

    def _run_demo(self, settings):
        if not self.server_ready.wait(timeout=5):
            self.event_queue.put(("status", "服务端启动超时"))
            self.event_queue.put(("demo_done", ""))
            return

        client_file = self.project_root / "client" / "client.exe"
        if not client_file.exists():
            self.event_queue.put(("status", "请先编译 client.exe"))
            self.event_queue.put(("demo_done", ""))
            return

        test_nodes = []
        node_count = settings["nodes_per_subtask"]
        subtask_count = settings["subtask_count"]

        for node_number in range(1, node_count + 1):
            node_id = f"node-{node_number:02d}"
            mode = "wrong" if node_number == node_count else "normal"
            test_nodes.append((node_id, mode))

        for round_number in range(1, subtask_count + 1):
            self.event_queue.put(
                (
                    "status",
                    f"{operation_label(settings['operation'])}："
                    f"第 {round_number}/{subtask_count} 个子任务",
                )
            )

            def run_node(node):
                node_id, mode = node
                result = subprocess.run(
                    [str(client_file), node_id, mode], cwd=self.project_root,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", creationflags=CREATE_NO_WINDOW,
                    check=False,
                )
                return node_id, result

            with ThreadPoolExecutor(max_workers=node_count) as workers:
                futures = [workers.submit(run_node, node) for node in test_nodes]
                completed_nodes = [future.result() for future in as_completed(futures)]

            for node_id, completed in sorted(completed_nodes):
                self.event_queue.put(
                    (
                        "client_log",
                        f"第{round_number}轮 {node_id}",
                        completed.stdout.strip(),
                    )
                )

                if completed.returncode != 0:
                    self.event_queue.put(
                        (
                            "status",
                            f"{node_id} 运行失败，退出码 {completed.returncode}",
                        )
                    )
                    self.event_queue.put(("demo_done", ""))
                    return

        self.event_queue.put(
            ("status", f"{operation_label(settings['operation'])}演示已完成")
        )
        self.event_queue.put(("demo_done", ""))
