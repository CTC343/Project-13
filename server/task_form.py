"""Build the task tabs and validate the values entered in the control center."""

import tkinter as tk
from tkinter import messagebox, ttk

from config import MALICIOUS_WRONG_ROUNDS
from operations import OPERATION_OPTIONS
from task_state import default_settings, validate_settings


FIELDS = (
    ("start", "起始值"),
    ("end", "最终值"),
    ("subtask_count", "子任务数"),
    ("nodes_per_subtask", "每个子任务的节点数"),
)


class TaskForm(ttk.Notebook):
    def __init__(self, parent, important, submit):
        super().__init__(parent)
        self._important = important
        self._defaults = default_settings()
        self._inputs = {}
        self._buttons = []
        for operation, label, description in OPERATION_OPTIONS:
            page = ttk.Frame(self, padding=18)
            self.add(page, text=label)
            self._build_page(page, operation, label, description, submit)

    def _build_page(self, page, operation, label, description, submit):
        ttk.Label(page, text=label, style="Heading.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 6)
        )
        ttk.Label(page, text=description).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 16)
        )

        variables = {}
        for index, (field, caption) in enumerate(FIELDS):
            row = 2 + index // 2
            column = (index % 2) * 2
            ttk.Label(page, text=f"{caption}（默认 {self._defaults[field]}）").grid(
                row=row, column=column, sticky="w", padx=(0, 10), pady=7,
            )
            variable = tk.StringVar(master=self)
            ttk.Entry(page, textvariable=variable, width=18).grid(
                row=row, column=column + 1, sticky="w", padx=(0, 30), pady=7,
            )
            variables[field] = variable
        self._inputs[operation] = variables

        button = ttk.Button(page, text=f"运行{label}完整流程", command=lambda: submit(operation))
        button.grid(row=4, column=0, columnspan=2, sticky="w", pady=(18, 8))
        self._buttons.append(button)

        ttk.Label(
            page,
            text=f"节点数至少为 3，连续异常检测需要至少 {MALICIOUS_WRONG_ROUNDS} 个子任务。",
        ).grid(row=5, column=0, columnspan=4, sticky="w")

    def read_settings(self, operation):
        """Use the service defaults for blank fields and its rules for validation."""
        settings = {"operation": operation, "important": self._important.get()}
        try:
            for field, variable in self._inputs[operation].items():
                text = variable.get().strip()
                settings[field] = int(text) if text else self._defaults[field]
        except ValueError:
            messagebox.showerror("输入错误", "所有输入项必须是整数。")
            return None

        try:
            validate_settings(settings)
        except ValueError as error:
            messagebox.showerror("输入错误", str(error))
            return None
        return settings

    def set_running(self, running):
        state = "disabled" if running else "normal"
        for button in self._buttons:
            button.configure(state=state)
