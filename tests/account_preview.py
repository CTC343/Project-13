"""End-to-end checks for the actual Win32 window and the server's Tk controls."""

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import secrets
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import patch


def wait_for(predicate, pump, seconds=15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        pump()
        if predicate():
            return
        time.sleep(0.04)
    raise AssertionError("Timed out waiting for a preview or account state")


class Win32Client:
    def __init__(self, executable):
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.enum_callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.api.EnumWindows.argtypes = self.enum_callback, wintypes.LPARAM
        self.api.EnumChildWindows.argtypes = wintypes.HWND, self.enum_callback, wintypes.LPARAM
        self.api.GetWindowThreadProcessId.argtypes = wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        self.api.GetClassNameW.argtypes = wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
        self.api.GetWindowLongW.argtypes = wintypes.HWND, ctypes.c_int
        self.api.SendMessageW.argtypes = wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        self.api.SendMessageW.restype = wintypes.LPARAM
        self.api.PostMessageW.argtypes = wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        self.api.GetDlgItem.argtypes = wintypes.HWND, ctypes.c_int
        self.api.GetDlgItem.restype = wintypes.HWND
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        self.process = subprocess.Popen([str(executable), "--window"], startupinfo=startup)
        self.window = None

    def find_window(self):
        @self.enum_callback
        def visit(handle, _):
            pid = wintypes.DWORD()
            self.api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if pid.value == self.process.pid and self.class_name(handle) == "Project13ClientWindow":
                self.window = handle
                return False
            return True

        if self.window is None:
            self.api.EnumWindows(visit, 0)
        return self.window

    def class_name(self, handle):
        output = ctypes.create_unicode_buffer(100)
        self.api.GetClassNameW(handle, output, len(output))
        return output.value

    def text(self, handle):
        output = ctypes.create_unicode_buffer(4096)
        self.api.SendMessageW(handle, 0x000D, len(output), ctypes.addressof(output))
        return output.value

    def login(self, username, password):
        fields = []

        @self.enum_callback
        def visit(handle, _):
            if self.class_name(handle) == "Edit":
                style = self.api.GetWindowLongW(handle, -16)
                if not style & 0x800 and not self.text(handle):
                    fields.append((handle, bool(style & 0x20)))
            return True

        self.api.EnumChildWindows(self.window, visit, 0)
        assert len(fields) == 2
        for field, masked in fields:
            text = ctypes.create_unicode_buffer(password if masked else username)
            try:
                assert self.api.SendMessageW(field, 0x000C, 0, ctypes.addressof(text))
            finally:
                ctypes.memset(ctypes.addressof(text), 0, ctypes.sizeof(text))
        assert self.api.PostMessageW(self.window, 0x0111, 103, 0)

    def allow(self, allowed):
        box = self.api.GetDlgItem(self.window, 110)
        assert box
        self.api.SendMessageW(box, 0x00F1, int(allowed), 0)
        assert self.api.PostMessageW(self.window, 0x0111, 110, box)

    def close(self):
        if self.process.poll() is None:
            if self.window:
                self.api.PostMessageW(self.window, 0x0010, 0, 0)
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=4)


def test_features(workspace, client_directory, launch_worker, task_history, evidence):
    from gui import ControlCenter
    from preview import REQUEST
    from runtime_log import recent_logs
    from security_audit import read_security_events

    password = secrets.token_urlsafe(24)
    username = "preview-fixture"
    console = ControlCenter()
    console.root.withdraw()
    client = None
    try:
        console.accounts.set_password("test-maintainer", "maintainer", None, password.encode())
        console.actor = "test-maintainer"
        console.role = console.accounts.verify(console.actor, password.encode())
        console._open_account_admin()
        admin = console.account_admin
        admin.window.withdraw()
        with patch("account_admin.NewAccountDialog", return_value=SimpleNamespace(result=(username, password.encode()))):
            admin.create()
        with patch("account_admin.NewAccountDialog",
                   return_value=SimpleNamespace(result=(username, secrets.token_bytes(24)))), \
             patch("account_admin.messagebox.showwarning") as warning:
            admin.create()
            assert warning.called
        wait_for(lambda: admin.table.exists(username), console.root.update)
        assert admin.table.item(username, "values")[1] == "离线"
        assert console.process_manager.start_server()
        wait_for(console.process_manager.is_server_running, console.root.update)
        client = Win32Client(client_directory / "client_gui.exe")
        wait_for(client.find_window, console.root.update)
        client.login(username, password)
        wait_for(lambda: admin.table.item(username, "values")[1] == "在线", console.root.update)
        assert tuple(map(int, admin.table.item(username, "values")[2:])) == (1, 1)
        assert admin.table.bind("<Double-1>")
        with patch.object(admin.table, "identify_row", return_value=username):
            admin.double_click(SimpleNamespace(y=0))
        viewer = admin.preview
        viewer.window.withdraw()
        wait_for(REQUEST.is_file, console.root.update)
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            console.root.update()
            assert viewer.source.frame() is None
            time.sleep(0.08)
        client.allow(True)
        wait_for(lambda: viewer.photo is not None, console.root.update)
        width, height = viewer.photo.width(), viewer.photo.height()
        assert width <= 960 and height <= 720
        colors = {viewer.photo.get(x, y) for x in range(0, width, 8) for y in range(0, height, 8)}
        assert len(colors) > 3, "the uploaded GUI frame is blank"
        first_sequence = viewer.sequence
        wait_for(lambda: (viewer.sequence or 0) > first_sequence, console.root.update)

        for label in ("demo-04", "demo-05"):
            launch_worker(label)
        wait_for(lambda: len(console.available_nodes) == 3, console.root.update)
        original_rounds = len(task_history())
        console.process_manager.submit_batch(
            {"operation": "SUM_RANGE", "start": 1, "end": 120, "subtask_count": 1,
             "nodes_per_subtask": 3, "important": False}, "demo-operator", "operator",
        )
        wait_for(lambda: len(task_history()) == original_rounds + 1, console.root.update)
        assert task_history()[-1]["integrated_result"] == 7260
        assert viewer.photo is not None
        client.allow(False)
        wait_for(lambda: viewer.photo is None, console.root.update)
        viewer.close()
        client.close()
        wait_for(lambda: admin.table.item(username, "values")[1] == "离线", console.root.update)
        console.process_manager.stop_server()
        wait_for(lambda: console.process_manager.server_process is None, console.root.update)
        assert recent_logs("INFO", "累计整合结果 7260")
        assert recent_logs("WARNING", "服务意外退出")
        stored = (Path(console.accounts.path).parent / "runtime.log").read_text(encoding="utf-8")
        assert password not in stored and "password_hex" not in stored
        assert "CLIENT_ACCOUNT_CREATED" in {event["event"] for event in read_security_events()}
        assert "WINDOW_PREVIEW_CLOSE" in {event["event"] for event in read_security_events()}
        restarted = ControlCenter()
        try:
            restarted.root.withdraw()
            assert "累计整合结果 7260" in restarted.log_box.get("1.0", "end")
        finally:
            restarted._close_window()
        evidence.update({
            "gui_account_creation_and_duplicate_rejection": True,
            "gui_account_online_and_offline": True,
            "double_click_opens_real_window_preview": True,
            "consent_can_start_and_stop_window_upload": True,
            "actual_png_size": [width, height],
            "task_completed_during_window_preview": 7260,
            "runtime_logs_searchable_after_console_restart": True,
        })
        (workspace / "account-preview-summary.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8",
        )
    finally:
        if client:
            client.close()
        console._close_window()
