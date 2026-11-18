"""Own exactly one supervised server process and open client watchdogs."""

import json
from logging import ERROR, INFO, WARNING
import os
import subprocess
import sys
import threading
import time
import uuid

from config import CLIENT_DIR, DATA_DIR, PROJECT_ROOT
from runtime_log import RuntimeLog
from security_audit import record_security_event

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ProcessManager:
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.server_process = None
        self.server_ready = threading.Event()
        self.lock = threading.Lock()
        self.stop_request = None
        self.runtime_log = RuntimeLog()

    def _log(self, level, message):
        self.event_queue.put(("runtime_log", self.runtime_log.write(level, message)))

    def start_server(self):
        with self.lock:
            if self.stop_request is not None:
                return False
            self.stop_request = threading.Event()
            self.server_ready.clear()
            threading.Thread(target=self._supervise_server, args=(self.stop_request,), daemon=True).start()
        self.event_queue.put(("status", "服务端正在启动"))
        return True

    def _supervise_server(self, stopped):
        environment = os.environ.copy()
        environment.update(PYTHONUTF8="1", PROJECT13_TASK_ENABLED="0")
        delay = 1
        while not stopped.is_set():
            try:
                with self.lock:
                    if stopped.is_set():
                        break
                    process = subprocess.Popen(
                        [sys.executable, "-B", "-u", str(PROJECT_ROOT / "server/server.py")],
                        cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace", env=environment,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    self.server_process = process
                started = time.monotonic()
                record_security_event("WATCHDOG_SERVER_STARTED", address="local", detail=f"pid={process.pid}")
                self._log(INFO, "服务进程已启动")
                with process.stdout:
                    for raw_line in process.stdout:
                        if stopped.is_set():
                            break
                        line = raw_line.rstrip("\r\n")
                        if line.startswith("READY:"):
                            self.server_ready.set()
                            self.event_queue.put(("status", "服务端运行中"))
                        self.event_queue.put(("server_line", line))
                        saved = self.runtime_log.from_server_line(line)
                        if saved:
                            self.event_queue.put(("runtime_log", saved))
                code = process.wait()
                self.server_ready.clear()
                if stopped.is_set():
                    break
                record_security_event("WATCHDOG_SERVER_EXITED", address="local",
                                      detail=f"pid={process.pid} exit={code} retry={delay}s")
                self._log(WARNING, f"服务意外退出，退出码 {code}，{delay} 秒后重试")
                self.event_queue.put(("server_recovering", f"服务端暂不可用，{delay} 秒后重试"))
                if time.monotonic() - started > 60:
                    delay = 1
            except OSError as error:
                self._log(ERROR, f"服务进程启动失败（错误号 {error.winerror if hasattr(error, 'winerror') else error.errno}）")
                self.event_queue.put(("status", f"服务端暂不可用，{delay} 秒后重试"))
                self.event_queue.put(("server_line", f"Service startup failed: {type(error).__name__}"))
            stopped.wait(delay)
            delay = min(delay * 2, 30)
        with self.lock:
            if self.stop_request is stopped:
                self.server_process = None
                self.stop_request = None
                self.server_ready.clear()

    def stop_server(self):
        with self.lock:
            if self.stop_request is None:
                return
            self.stop_request.set()
            process = self.server_process
            self.server_ready.clear()
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        record_security_event("WATCHDOG_SERVER_STOPPED", address="local", detail="controlled stop")
        self._log(INFO, "服务已停止")
        self.event_queue.put(("server_stopped", "服务端已停止"))

    def submit_batch(self, settings, actor, role):
        if role != "operator":
            raise PermissionError("Only an operator may submit a batch.")
        if not self.is_server_running():
            raise RuntimeError("The service is unavailable.")
        request = DATA_DIR / "commands" / (uuid.uuid4().hex + ".json")
        temporary = request.with_suffix(".tmp")
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump({"settings": settings, "actor": actor, "role": role}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(request)

    def open_client_window(self):
        client = CLIENT_DIR / "client_gui.exe"
        if not client.is_file():
            self.event_queue.put(("status", "请先构建客户端"))
            return
        subprocess.Popen([str(client)], cwd=CLIENT_DIR)
        self.event_queue.put(("status", "已打开客户端窗口"))

    def is_server_running(self):
        return self.server_ready.is_set() and self.server_process is not None and self.server_process.poll() is None
