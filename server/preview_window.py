"""Read and display the current frame from the server's local preview mapping."""

import base64
import time
import tkinter as tk
from tkinter import ttk

from preview import PreviewSource
from security_audit import record_security_event


class PreviewWindow:
    def __init__(self, parent, username, node_id, actor, online):
        self.source = PreviewSource(node_id)
        self.window = tk.Toplevel(parent)
        self.window.title(f"窗口预览 · {username}")
        self.window.geometry("1000x750")
        self.window.minsize(420, 300)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.node_id, self.actor, self.online = node_id, actor, online
        self.status = ttk.Label(self.window, style="Heading.TLabel", padding=12)
        self.status.pack(fill="x")
        self.image = ttk.Label(self.window, anchor="center")
        self.image.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.photo = None
        self.sequence = None
        self.timer = None
        self.closed = False
        record_security_event("WINDOW_PREVIEW_OPEN", self.node_id, "local", actor)
        self.refresh()

    def refresh(self):
        self.source.renew()
        frame = self.source.frame()
        if not self.online(self.node_id):
            self.show_waiting("节点离线，等待重新连接")
        elif frame is None:
            self.show_waiting("等待客户端勾选 Allow window preview")
        else:
            sequence, captured, image = frame
            if time.monotonic() - captured > 3:
                self.show_waiting("画面已中断，等待客户端继续共享")
            elif not image:
                self.show_waiting("暂时无法获取画面，请确认客户端窗口未最小化")
            elif sequence != self.sequence:
                try:
                    self.photo = tk.PhotoImage(
                        master=self.window, data=base64.b64encode(image), format="png",
                    )
                    self.image.configure(image=self.photo, text="")
                    self.status.configure(text=f"实时预览  ·  {self.node_id}")
                    self.sequence = sequence
                except tk.TclError:
                    self.show_waiting("画面格式错误，等待下一帧")
        self.timer = self.window.after(200, self.refresh)

    def show_waiting(self, text):
        self.image.configure(image="", text=text)
        self.status.configure(text=self.node_id)
        self.photo = None
        self.sequence = None

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.timer:
            self.window.after_cancel(self.timer)
        self.source.close()
        self.window.destroy()
        record_security_event("WINDOW_PREVIEW_CLOSE", self.node_id, "local", self.actor)
