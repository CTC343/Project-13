"""Client account creation, presence list and preview selection for maintainers."""

import sqlite3
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from accounts import ACCOUNT_ID
from preview_window import PreviewWindow
from security_audit import record_security_event


class NewAccountDialog(simpledialog.Dialog):
    def body(self, frame):
        self.username = tk.StringVar(self)
        self.password = tk.StringVar(self)
        self.confirmation = tk.StringVar(self)
        first = None
        for index, (label, variable, hidden) in enumerate((
            ("账号", self.username, False),
            ("口令", self.password, True),
            ("确认口令", self.confirmation, True),
        )):
            ttk.Label(frame, text=label).grid(row=index, column=0, padx=(0, 12), pady=5, sticky="w")
            entry = ttk.Entry(frame, textvariable=variable, show="*" if hidden else "", width=31)
            entry.grid(row=index, column=1, pady=5, sticky="ew")
            if first is None:
                first = entry
        ttk.Label(frame, text="账号限英文字母、数字、- 和 _；口令至少 12 字节。").grid(
            row=3, columnspan=2, pady=(8, 0), sticky="w",
        )
        return first

    def validate(self):
        username = self.username.get().strip()
        password = self.password.get()
        if not ACCOUNT_ID.fullmatch(username):
            messagebox.showwarning("账号格式", "请输入 1–63 个英文字母、数字、- 或 _。", parent=self)
            return False
        if password != self.confirmation.get():
            messagebox.showwarning("口令不一致", "请重新确认口令。", parent=self)
            return False
        if not 12 <= len(password.encode("utf-8")) <= 256 or not password.strip():
            messagebox.showwarning("口令长度", "请输入 12–256 字节的口令。", parent=self)
            return False
        return True

    def apply(self):
        self.result = (self.username.get().strip(), self.password.get().encode("utf-8"))
        self.password.set("")
        self.confirmation.set("")


class DeviceDialog(simpledialog.Dialog):
    def __init__(self, parent, nodes):
        self.nodes = nodes
        super().__init__(parent, "选择在线设备")

    def body(self, frame):
        ttk.Label(frame, text="此账号有多台设备在线，请选一台。").pack(anchor="w", pady=(0, 8))
        self.selection = tk.StringVar(self, value=self.nodes[0])
        device = ttk.Combobox(frame, textvariable=self.selection, values=self.nodes, state="readonly", width=38)
        device.pack(fill="x")
        return device

    def apply(self):
        self.result = self.selection.get()


class AccountAdmin:
    def __init__(self, parent, store, actor, online, authorized):
        self.store, self.actor, self.online, self.authorized = store, actor, online, authorized
        self.preview = None
        self.accounts = {}
        self.window = tk.Toplevel(parent)
        self.window.title("客户端账号管理")
        self.window.geometry("760x490")
        self.window.minsize(540, 350)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.timer = None
        self.closed = False
        panel = ttk.Frame(self.window, padding=16)
        panel.pack(fill="both", expand=True)
        actions = ttk.Frame(panel)
        actions.pack(fill="x", pady=(0, 12))
        ttk.Button(actions, text="创建客户端账号", command=self.create).pack(side="left")
        ttk.Button(actions, text="查看窗口", command=self.open_selected).pack(side="left", padx=(10, 0))
        self.feedback = ttk.Label(actions)
        self.feedback.pack(side="right")

        table_area = ttk.Frame(panel)
        table_area.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_area, columns=("username", "state", "online", "registered"),
                                 show="headings", selectmode="browse")
        for name, caption, width in (("username", "客户端账号", 230), ("state", "状态", 90),
                                     ("online", "在线设备", 100), ("registered", "已登记设备", 110)):
            self.table.heading(name, text=caption)
            self.table.column(name, width=width, anchor="w")
        scrollbar = ttk.Scrollbar(table_area, command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.bind("<Double-1>", self.double_click)
        self.refresh()

    def refresh(self):
        if not self.authorized():
            self.close()
            return
        try:
            self.accounts = self.store.list_node_accounts()
            existing = set(self.table.get_children())
            for username, devices in self.accounts.items():
                count = sum(self.online(node_id) for node_id in devices)
                values = username, "在线" if count else "离线", count, len(devices)
                if username in existing:
                    self.table.item(username, values=values)
                else:
                    self.table.insert("", "end", iid=username, values=values)
            for username in existing - self.accounts.keys():
                self.table.delete(username)
        except sqlite3.Error:
            self.feedback.configure(text="暂时无法读取账号库")
        self.timer = self.window.after(1000, self.refresh)

    def create(self):
        if not self.authorized():
            return
        dialog = NewAccountDialog(self.window, "创建客户端账号")
        if not dialog.result or not self.authorized():
            return
        username, password = dialog.result
        dialog.result = None
        try:
            self.store.create_node_account(username, password)
            record_security_event("CLIENT_ACCOUNT_CREATED", self.actor, "local", f"account={username} role=node")
        except (ValueError, sqlite3.Error) as error:
            messagebox.showwarning("创建失败", str(error), parent=self.window)
            return
        self.feedback.configure(text=f"已创建 {username}")

    def double_click(self, event):
        username = self.table.identify_row(event.y)
        if username:
            self.open_preview(username)

    def open_selected(self):
        selection = self.table.selection()
        if selection:
            self.open_preview(selection[0])

    def open_preview(self, username):
        if not self.authorized():
            return
        candidates = [node for node in self.accounts.get(username, ()) if self.online(node)]
        if not candidates:
            self.feedback.configure(text=f"{username} 当前离线")
            return
        node = DeviceDialog(self.window, candidates).result if len(candidates) > 1 else candidates[0]
        if not node or not self.authorized():
            return
        if self.preview:
            self.preview.close()
        try:
            self.preview = PreviewWindow(self.window, username, node, self.actor, self.online)
        except OSError as error:
            messagebox.showwarning("无法打开预览", str(error), parent=self.window)

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.timer:
            self.window.after_cancel(self.timer)
        if self.preview:
            self.preview.close()
        self.window.destroy()
