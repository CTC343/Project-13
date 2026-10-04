"""项目13服务端控制中心。只负责界面，进程操作放在 process_manager.py。"""

import queue
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from audit import read_rounds
from config import (
    HOST,
    INITIAL_REPUTATION,
    MALICIOUS_WRONG_ROUNDS,
    PORT,
    REQUIRED_NODES,
    TASK_END,
    TASK_ID_PREFIX,
    TASK_START,
    TOTAL_ROUNDS,
)
from evaluation import read_evaluation_report
from operations import OPERATION_OPTIONS, expected_result, operation_label
from process_manager import ProcessManager
from security_audit import read_security_events
from security_tests import create_report, read_security_test_report


class ControlCenter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("项目13 服务端控制中心")
        self.root.geometry("1080x760")
        self.root.minsize(900, 620)

        self.event_queue = queue.Queue()
        self.process_manager = ProcessManager(self.event_queue)

        self.status_text = tk.StringVar(value="服务端未运行")
        self.majority_text = tk.StringVar(value="尚未完成表决")
        self.integrated_text = tk.StringVar(value="总任务结果尚未整合")
        self.malicious_text = tk.StringVar(value="尚未发现持续异常节点")
        self.allocation_text = tk.StringVar(value="重要任务尚未调度")
        self.node_rows = {}
        self.operation_inputs = {}
        self.demo_buttons = []
        self.status_rows = {}

        self._configure_style()
        self._build_page()
        self.root.protocol("WM_DELETE_WINDOW", self._close_window)
        self.root.after(100, self._read_events)

    def run(self):
        self.root.mainloop()

    def _configure_style(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10))
        style.configure("TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("Treeview", font=("Microsoft YaHei UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_page(self):
        header = ttk.Frame(self.root, padding=(20, 16, 20, 10))
        header.pack(fill="x")
        ttk.Label(header, text="项目13 服务端控制中心", style="Title.TLabel").pack(
            side="left"
        )
        ttk.Label(header, textvariable=self.status_text).pack(side="right")

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        control_tab = ttk.Frame(notebook, padding=20)
        result_tab = ttk.Frame(notebook, padding=20)
        node_tab = ttk.Frame(notebook, padding=20)
        log_tab = ttk.Frame(notebook, padding=12)
        audit_tab = ttk.Frame(notebook, padding=20)
        evaluation_tab = ttk.Frame(notebook, padding=20)
        security_tab = ttk.Frame(notebook, padding=20)
        future_tab = ttk.Frame(notebook, padding=20)

        notebook.add(control_tab, text="运行控制")
        notebook.add(result_tab, text="结果与信誉")
        notebook.add(node_tab, text="节点在线状态")
        notebook.add(log_tab, text="系统日志")
        notebook.add(audit_tab, text="审计记录")
        notebook.add(evaluation_tab, text="项目考核")
        notebook.add(security_tab, text="安全自检")
        notebook.add(future_tab, text="模块状态")

        self._build_control_tab(control_tab)
        self._build_result_tab(result_tab)
        self._build_node_tab(node_tab)
        self._build_log_tab(log_tab)
        self._build_audit_tab(audit_tab)
        self._build_evaluation_tab(evaluation_tab)
        self._build_security_tab(security_tab)
        self._build_future_tab(future_tab)

    def _build_control_tab(self, parent):
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(0, 14))

        ttk.Button(
            button_frame, text="按默认参数启动服务", command=self._start_server
        ).pack(side="left", padx=(0, 10))
        ttk.Button(
            button_frame, text="停止服务", command=self.process_manager.stop_server
        ).pack(side="left", padx=(0, 10))

        ttk.Button(
            button_frame,
            text="打开客户端窗口",
            command=self.process_manager.open_client_window,
        ).pack(side="left")

        ttk.Label(
            parent,
            text=(
                f"监听 {HOST}:{PORT}；任务水印格式为 "
                f"{TASK_ID_PREFIX}-随机会话号-子任务号。"
                "选择下面的运算并运行，留空输入项会使用括号内默认值。"
            ),
            wraplength=850,
        ).pack(anchor="w", pady=(0, 12))

        operation_notebook = ttk.Notebook(parent)
        operation_notebook.pack(fill="both", expand=True)

        for operation, label, description in OPERATION_OPTIONS:
            operation_tab = ttk.Frame(operation_notebook, padding=18)
            operation_notebook.add(operation_tab, text=label)
            self._build_operation_form(
                operation_tab, operation, label, description
            )

    def _build_operation_form(self, parent, operation, label, description):
        ttk.Label(parent, text=label, style="Heading.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 6)
        )
        ttk.Label(parent, text=description).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 16)
        )

        field_definitions = [
            ("start", "起始值", TASK_START),
            ("end", "最终值", TASK_END),
            ("subtask_count", "子任务数", TOTAL_ROUNDS),
            ("nodes_per_subtask", "每个子任务的节点数", REQUIRED_NODES),
        ]
        input_variables = {}

        for index, (field_name, field_label, default_value) in enumerate(
            field_definitions
        ):
            row_number = 2 + index // 2
            column_number = (index % 2) * 2
            ttk.Label(
                parent, text=f"{field_label}（默认 {default_value}）"
            ).grid(
                row=row_number,
                column=column_number,
                sticky="w",
                padx=(0, 10),
                pady=7,
            )
            variable = tk.StringVar()
            ttk.Entry(parent, textvariable=variable, width=18).grid(
                row=row_number,
                column=column_number + 1,
                sticky="w",
                padx=(0, 30),
                pady=7,
            )
            input_variables[field_name] = variable

        self.operation_inputs[operation] = input_variables
        run_button = ttk.Button(
            parent,
            text=f"运行{label}完整流程",
            command=lambda code=operation: self._run_operation_demo(code),
        )
        run_button.grid(row=4, column=0, columnspan=2, sticky="w", pady=(18, 8))
        self.demo_buttons.append(run_button)

        ttk.Label(
            parent,
            text=(
                f"节点数至少为 3；连续异常检测需要至少 "
                f"{MALICIOUS_WRONG_ROUNDS} 个子任务。"
            ),
        ).grid(row=5, column=0, columnspan=4, sticky="w")

    def _read_operation_settings(self, operation):
        variables = self.operation_inputs[operation]
        defaults = {
            "start": TASK_START,
            "end": TASK_END,
            "subtask_count": TOTAL_ROUNDS,
            "nodes_per_subtask": REQUIRED_NODES,
        }
        settings = {"operation": operation}

        try:
            for field_name, default_value in defaults.items():
                text = variables[field_name].get().strip()
                settings[field_name] = int(text) if text else default_value
        except ValueError:
            messagebox.showerror("输入错误", "所有输入项必须是整数。")
            return None

        number_count = settings["end"] - settings["start"] + 1
        if number_count < 1:
            messagebox.showerror("输入错误", "最终值必须大于或等于起始值。")
            return None
        if number_count > 2000000:
            messagebox.showerror("输入错误", "演示范围暂时不能超过 200 万个数。")
            return None
        if number_count < settings["subtask_count"] * 4:
            messagebox.showerror(
                "输入错误", "为了生成四步 Merkle 证明，每个子任务至少需要 4 个数。"
            )
            return None
        if not 3 <= settings["nodes_per_subtask"] <= 50:
            messagebox.showerror("输入错误", "每个子任务的节点数必须在 3 到 50 之间。")
            return None

        final_value = expected_result(
            operation, settings["start"], settings["end"]
        )
        if not -2147483648 <= final_value <= 2147483647:
            messagebox.showerror("输入错误", "结果超出当前 C 客户端整数范围。")
            return None

        return settings

    def _run_operation_demo(self, operation):
        settings = self._read_operation_settings(operation)
        if settings is None:
            return

        self._clear_results()
        for button in self.demo_buttons:
            button.configure(state="disabled")
        self.process_manager.restart_and_run_demo(settings)

    def _build_result_tab(self, parent):
        ttk.Label(parent, textvariable=self.majority_text,
                  style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(parent, textvariable=self.integrated_text).pack(
            anchor="w", pady=(0, 12)
        )
        ttk.Label(parent, textvariable=self.malicious_text).pack(
            anchor="w", pady=(0, 12)
        )
        ttk.Label(parent, textvariable=self.allocation_text).pack(
            anchor="w", pady=(0, 12)
        )

        self.result_table = ttk.Treeview(
            parent,
            columns=("node", "result", "reputation", "status"),
            show="headings",
            height=12,
        )
        self.result_table.heading("node", text="节点 ID")
        self.result_table.heading("result", text="返回结果")
        self.result_table.heading("reputation", text="信誉分")
        self.result_table.heading("status", text="识别状态")
        self.result_table.column("node", width=170, anchor="center")
        self.result_table.column("result", width=170, anchor="center")
        self.result_table.column("reputation", width=170, anchor="center")
        self.result_table.column("status", width=170, anchor="center")
        self.result_table.pack(fill="both", expand=True)

    def _build_log_tab(self, parent):
        self.log_box = tk.Text(
            parent,
            wrap="word",
            font=("Consolas", 10),
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(parent, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scrollbar.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_node_tab(self, parent):
        ttk.Label(
            parent,
            text="节点登录、心跳和任务状态（由服务端实时更新）",
            style="Heading.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        self.node_status_table = ttk.Treeview(
            parent,
            columns=("node", "login", "state", "heartbeat", "address"),
            show="headings",
            height=15,
        )
        headings = {
            "node": "节点 ID", "login": "登录状态", "state": "当前状态",
            "heartbeat": "最近心跳", "address": "连接地址",
        }
        widths = {
            "node": 140, "login": 150, "state": 130,
            "heartbeat": 210, "address": 170,
        }
        for name, text in headings.items():
            self.node_status_table.heading(name, text=text)
            self.node_status_table.column(name, width=widths[name], anchor="center")
        self.node_status_table.pack(fill="both", expand=True)

    def _build_audit_tab(self, parent):
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(0, 12))
        ttk.Label(
            button_frame,
            text="每完成一轮保存一条记录",
            style="Heading.TLabel",
        ).pack(side="left")
        ttk.Button(
            button_frame, text="刷新", command=self._refresh_audit
        ).pack(side="right")

        self.audit_table = ttk.Treeview(
            parent,
            columns=(
                "round",
                "operation",
                "task",
                "trusted",
                "integrated",
                "results",
                "malicious",
            ),
            show="headings",
            height=13,
        )
        headings = {
            "round": "轮次",
            "operation": "运算",
            "task": "任务编号",
            "trusted": "子任务可信结果",
            "integrated": "累计整合结果",
            "results": "节点结果",
            "malicious": "异常节点",
        }
        widths = {
            "round": 70,
            "operation": 100,
            "task": 110,
            "trusted": 110,
            "integrated": 120,
            "results": 260,
            "malicious": 120,
        }
        for column_name in headings:
            self.audit_table.heading(column_name, text=headings[column_name])
            self.audit_table.column(
                column_name, width=widths[column_name], anchor="center"
            )
        self.audit_table.pack(fill="both", expand=True)
        self._refresh_audit()

    def _build_evaluation_tab(self, parent):
        ttk.Label(
            parent,
            text="对照题目给出的三项考核要求",
            style="Heading.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        self.evaluation_table = ttk.Treeview(
            parent,
            columns=("metric", "value", "requirement", "result"),
            show="headings",
            height=8,
        )
        self.evaluation_table.heading("metric", text="考核项目")
        self.evaluation_table.heading("value", text="实测值")
        self.evaluation_table.heading("requirement", text="要求")
        self.evaluation_table.heading("result", text="结论")
        self.evaluation_table.column("metric", width=200, anchor="center")
        self.evaluation_table.column("value", width=180, anchor="center")
        self.evaluation_table.column("requirement", width=220, anchor="center")
        self.evaluation_table.column("result", width=120, anchor="center")
        self.evaluation_table.pack(fill="both", expand=True)

        ttk.Button(
            parent, text="刷新考核结果", command=self._refresh_evaluation
        ).pack(anchor="e", pady=(12, 0))
        self._refresh_evaluation()

    def _build_security_tab(self, parent):
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(
            button_frame, text="安全边界自检", style="Heading.TLabel"
        ).pack(side="left")
        ttk.Button(
            button_frame, text="运行全部安全自检",
            command=self._run_security_tests,
        ).pack(side="right")

        self.security_test_table = ttk.Treeview(
            parent, columns=("case", "result", "detail"),
            show="headings", height=9,
        )
        self.security_test_table.heading("case", text="测试场景")
        self.security_test_table.heading("result", text="结果")
        self.security_test_table.heading("detail", text="说明")
        self.security_test_table.column("case", width=250, anchor="w")
        self.security_test_table.column("result", width=90, anchor="center")
        self.security_test_table.column("detail", width=430, anchor="w")
        self.security_test_table.pack(fill="x")

        ttk.Label(
            parent, text="安全事件审计", style="Heading.TLabel"
        ).pack(anchor="w", pady=(18, 8))
        self.security_event_table = ttk.Treeview(
            parent, columns=("time", "event", "node", "detail"),
            show="headings", height=7,
        )
        for name, text, width in (
            ("time", "时间", 170), ("event", "事件", 150),
            ("node", "节点", 120), ("detail", "详情", 430),
        ):
            self.security_event_table.heading(name, text=text)
            self.security_event_table.column(name, width=width, anchor="w")
        self.security_event_table.pack(fill="both", expand=True)
        self._refresh_security()

    def _build_future_tab(self, parent):
        ttk.Label(
            parent,
            text="项目要求模块状态",
            style="Heading.TLabel",
        ).pack(anchor="w", pady=(0, 14))

        future_modules = [
            ("任务拆解", "已完成", "总区间拆成五个子任务并整合结果"),
            ("多轮任务", "已完成", "连续五轮并保留跨轮次信誉"),
            ("审计记录", "已完成", "每轮保存表决、信誉和异常节点"),
            ("任务签名", "已完成", "唯一水印、服务端私钥签名和客户端验签"),
            ("Merkle Tree", "已完成", "四段计算步骤和根哈希验证"),
            ("信誉调度", "已完成", "低信誉节点不再接收重要任务"),
            ("并发与重连", "已完成", "线程池并发处理，客户端三次有限重连"),
            ("登录与心跳", "已完成", "节点凭据认证、在线状态和心跳记录"),
            ("私有协议", "已完成", "P13/1 Header + JSON Body + 状态码"),
            ("安全会话", "已完成", "加密、消息认证、序号和随机数抗重放"),
            ("软件保护", "已完成", "许可证绑定和程序哈希完整性白名单"),
            ("安全测试", "已完成", "重放、篡改、伪造身份和非法输入自检"),
            ("TEE 报告", "选做未启用", "题目注明选做，本轮不模拟"),
        ]

        table = ttk.Treeview(
            parent,
            columns=("module", "status", "description"),
            show="headings",
            height=15,
        )
        table.heading("module", text="模块")
        table.heading("status", text="状态")
        table.heading("description", text="接入内容")
        table.column("module", width=160, anchor="center")
        table.column("status", width=100, anchor="center")
        table.column("description", width=500, anchor="w")
        table.pack(fill="both", expand=True)

        for module_name, status, description in future_modules:
            table.insert("", "end", values=(module_name, status, description))

    def _start_server(self):
        if self.process_manager.start_server():
            self._clear_results()

    def _clear_results(self):
        for row_id in self.result_table.get_children():
            self.result_table.delete(row_id)
        self.node_rows.clear()
        self.majority_text.set("尚未完成表决")
        self.integrated_text.set("总任务结果尚未整合")
        self.malicious_text.set("尚未发现持续异常节点")
        self.allocation_text.set("重要任务尚未调度")

    def _read_events(self):
        while True:
            try:
                event = self.event_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

        self.root.after(100, self._read_events)

    def _handle_event(self, event):
        event_type = event[0]

        if event_type == "status":
            self.status_text.set(event[1])
        elif event_type == "server_line":
            self._append_log(f"[server] {event[1]}\n")
            self._read_server_line(event[1])
        elif event_type == "client_log":
            node_id = event[1]
            output = event[2]
            self._append_log(f"[{node_id}]\n{output}\n")
        elif event_type == "server_stopped":
            if not self.process_manager.is_server_running():
                self.status_text.set(event[1])
        elif event_type == "demo_done":
            for button in self.demo_buttons:
                button.configure(state="normal")
            self._refresh_audit()
            self._refresh_evaluation()
            self._refresh_security()

    def _read_server_line(self, line):
        status_match = re.match(
            r"NODE_STATUS (\S+) login=(\S+) state=(\S+) "
            r"heartbeat=(\S+) address=(\S+)", line
        )
        if status_match:
            self._set_status_value(*status_match.groups())
            return

        result_match = re.match(r"Result \d+/\d+: (\S+) -> (-?\d+)", line)
        if result_match:
            node_id = result_match.group(1)
            result_value = result_match.group(2)
            self._set_node_value(node_id, result=result_value)
            return

        reputation_match = re.match(
            r"Reputation: (\S+) \d+ -> (\d+)", line
        )
        if reputation_match:
            node_id = reputation_match.group(1)
            reputation = reputation_match.group(2)
            self._set_node_value(node_id, reputation=reputation)
            return

        if line.startswith("Majority result:"):
            majority_value = line.split(":", 1)[1].strip()
            self.majority_text.set(f"多数表决可信结果：{majority_value}")
        elif line.startswith("Integrated result:"):
            integrated_value = line.split(":", 1)[1].strip()
            self.integrated_text.set(f"当前累计整合结果：{integrated_value}")
        elif line.startswith("Vote failed:"):
            self.majority_text.set("多数表决失败：没有两个一致结果")
        elif line.startswith("Malicious node detected:"):
            node_id = line.split(":", 1)[1].strip()
            self._set_node_value(node_id, status="持续异常")
            self.malicious_text.set(f"已识别持续异常节点：{node_id}")
        elif line.startswith("Important-task excluded:"):
            node_text = line.split(":", 1)[1].strip()
            excluded_nodes = [
                node.strip() for node in node_text.split(",") if node.strip()
            ]
            for node_id in excluded_nodes:
                self._set_node_value(node_id, status="不分配重要任务")
            self.allocation_text.set(
                "重要任务排除节点：" + (node_text or "无")
            )
        elif line.startswith("Audit saved:"):
            self._refresh_audit()
        elif line.startswith("Evaluation malicious ratio:"):
            self._refresh_evaluation()

    def _set_node_value(
        self, node_id, result=None, reputation=None, status=None
    ):
        if node_id not in self.node_rows:
            row_id = self.result_table.insert(
                "", "end", values=(node_id, "等待", INITIAL_REPUTATION, "正常")
            )
            self.node_rows[node_id] = row_id

        row_id = self.node_rows[node_id]
        old_values = list(self.result_table.item(row_id, "values"))

        if result is not None:
            old_values[1] = result
        if reputation is not None:
            old_values[2] = reputation
        if status is not None:
            old_values[3] = status

        self.result_table.item(row_id, values=old_values)

    def _set_status_value(self, node_id, login, state, heartbeat, address):
        translations = {
            "authenticated": "认证通过", "rejected": "认证拒绝",
            "signed_out": "已退出", "online": "在线",
            "heartbeat": "心跳正常", "computing": "计算中",
            "completed": "已提交", "offline": "离线",
            "waiting": "在线等待任务",
        }
        values = (
            node_id, translations.get(login, login),
            translations.get(state, state), heartbeat, address,
        )
        if node_id not in self.status_rows:
            self.status_rows[node_id] = self.node_status_table.insert(
                "", "end", values=values
            )
        else:
            self.node_status_table.item(self.status_rows[node_id], values=values)

    def _append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _refresh_audit(self):
        for row_id in self.audit_table.get_children():
            self.audit_table.delete(row_id)

        for record in read_rounds():
            results = ", ".join(
                f"{node}: {value}"
                for node, value in record.get("results", {}).items()
            )
            malicious = ", ".join(record.get("malicious_nodes", []))
            self.audit_table.insert(
                "",
                "end",
                values=(
                    record.get("round", ""),
                    operation_label(record.get("operation", "")),
                    record.get("task_id", ""),
                    record.get("trusted_value", ""),
                    record.get("integrated_result", ""),
                    results,
                    malicious or "无",
                ),
            )

    def _refresh_evaluation(self):
        for row_id in self.evaluation_table.get_children():
            self.evaluation_table.delete(row_id)

        report = read_evaluation_report()
        if not report:
            self.evaluation_table.insert(
                "", "end", values=("等待五轮演示", "-", "-", "未运行")
            )
            return

        rows = [
            (
                "当前运算",
                operation_label(report.get("operation", "")),
                "所选任务",
                "已完成",
            ),
            (
                "结果准确性误差",
                f"{report['accuracy_error_percent']:.2f}%",
                "小于 1%",
                "通过" if report["accuracy_passed"] else "未通过",
            ),
            (
                "安全机制时间开销",
                f"{report['security_overhead_percent']:.2f}%",
                "不超过 30%",
                "通过" if report["security_overhead_passed"] else "未通过",
            ),
            (
                "恶意节点比例与识别",
                f"{report['malicious_ratio_percent']:.2f}%",
                "比例不超过 10%，五轮内识别",
                "通过" if report["malicious_detection_passed"] else "未通过",
            ),
        ]
        for row in rows:
            self.evaluation_table.insert("", "end", values=row)

    def _run_security_tests(self):
        report = create_report()
        self._refresh_security()
        result_text = f"{report['passed']}/{report['total']} 项通过"
        if report["all_passed"]:
            messagebox.showinfo("安全自检", result_text)
        else:
            messagebox.showwarning("安全自检", result_text)

    def _refresh_security(self):
        for row_id in self.security_test_table.get_children():
            self.security_test_table.delete(row_id)
        report = read_security_test_report()
        if not report:
            self.security_test_table.insert(
                "", "end", values=("尚未运行", "-", "点击右上角按钮")
            )
        else:
            for item in report.get("results", []):
                self.security_test_table.insert(
                    "", "end", values=(
                        item.get("name", ""),
                        "通过" if item.get("passed") else "失败",
                        item.get("detail", ""),
                    )
                )

        for row_id in self.security_event_table.get_children():
            self.security_event_table.delete(row_id)
        for item in read_security_events()[-100:]:
            self.security_event_table.insert(
                "", "end", values=(
                    item.get("time", ""), item.get("event", ""),
                    item.get("node_id", ""), item.get("detail", ""),
                )
            )

    def _close_window(self):
        self.process_manager.stop_server()
        self.root.destroy()


def check_files():
    project_root = Path(__file__).resolve().parent.parent
    required_files = [
        project_root / "server" / "server.py",
        project_root / "client" / "client.exe",
        project_root / "client" / "client_gui.exe",
    ]

    missing_files = [str(path) for path in required_files if not path.exists()]
    if missing_files:
        print("Missing UI dependency:")
        for path in missing_files:
            print(path)
        return 1

    print("UI dependency check: OK")
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(check_files())

    ControlCenter().run()
