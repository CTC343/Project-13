# 服务端代码说明

[server/gui.py](server/gui.py) 是控制中心入口。[server/server.py](server/server.py) 是实际监听端口、处理客户端连接的服务进程。运行环境、证书和账号的初始化命令见 [README](README.md)，逐个文件的用途见 [目录树](目录树.txt)，消息格式见 [通信协议](PROTOCOL.md)。

## 从登录到任务完成

1. `server.py` 默认监听 `0.0.0.0:8888` 和 `0.0.0.0:8889`。业务端口使用双向 TLS 1.3，第一条业务消息可以是任务登录 `AUTH` 或窗口预览 `PREVIEW_OPEN`。相邻的登记端口由 `enrollment.py` 处理首次登录和设备证书签发。
2. `task_service.py` 验证节点证书、客户端可执行文件哈希、账号和设备绑定关系，并用口令或会话令牌确认登录。连接结束后，节点占用和预览请求都随之清理。
3. `task_form.py` 负责任务的输入表单，`task_state.py` 提供表单和服务端共用的默认值与校验规则。操作员提交后，`process_manager.py` 把任务请求写入服务端本地命令目录，由 `server.py` 读取。
4. `scheduler.py` 锁定当前轮次、检查节点信誉并预留名额。它通过 `task_planner.py` 取得本轮子区间。任务签名由 `signature.py` 生成，`task_service.py` 负责发送任务、处理心跳和等待消息。
5. `task_results.py` 校验任务和节点编号、检查 Merkle 证明并保存结果。相同的重传复用已保存的回执，过期结果回复 `RETAIN`。收齐要求的结果后，严格多数决议产生可信结果并更新信誉。未形成多数时，记录该轮失败并结束批次。
6. `operations.py` 负责合并各轮结果。结果、轮次审计和任务检查点在同一事务提交，之后才回复客户端。重启后，`task_state.py` 从 SQLite 恢复任务与信誉。

## 修改时从哪里入手

| 目标 | 对应模块 |
| --- | --- |
| 新增运算 | `server/operations.py` 登记运算名、期望值和合并方式，`client/operations.c` 实现同名计算，同时核对两端的证明规则。 |
| 修改输入项或参数限制 | `task_form.py` 管理表单，`task_state.py` 管理默认值和后端校验。 |
| 调整任务区间或节点资格 | `task_planner.py` 处理区间划分，`scheduler.py` 管理节点资格和名额。 |
| 调整表决、信誉或结果恢复规则 | `task_results.py`。 |
| 查看结果、考核和日志 | `audit.py` 和 `evaluation.py` 从任务库读取结果，`runtime_log.py` 保存运行日志，`security_audit.py` 保存安全事件。 |
| 修改账号或预览 | `accounts.py` 和 `account_admin.py` 管理账号。服务端的 `preview.py` 和 `preview_window.py` 管理预览请求和显示，客户端的 `preview.c` 负责授权与抓取窗口。 |

控制中心可以运行 `python -B .\server\gui.py` 打开。任务库 `data/runtime/tasks.sqlite3` 保存任务批次、结果、信誉和审计。账号库、TLS 私钥和任务签名私钥的生成方式见 [README](README.md#本地生成的保密文件和运行数据)。
