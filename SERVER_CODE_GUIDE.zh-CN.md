# 服务端代码说明

本文介绍 `server/` 目录下的 Python 服务端代码，**不包含**
`server/gui.py`。C 语言客户端及其图形界面也不在本文范围内。网络消息格式
请参阅[通信协议文档](./PROTOCOL.md)。

## 服务端的作用

服务端将整数区间计算分发给经过身份验证的客户端节点。它把配置的区间拆分为
多个子任务，将每个子任务分配给多个不同节点，验证节点提交的结果证明，再通过
严格多数表决选出可信结果，合并各子任务结果，并保存审计和考核数据。

主要入口是 [server/server.py](./server/server.py)。该模块监听配置的 TCP
地址，接收连接，并将每个连接交给任务服务处理。服务端使用线程池，因此多个
节点可以并发登录、发送心跳和提交结果。

## 请求与任务处理流程

1. **启动并验证配置。** `server.py` 在启动监听器前检查运算类型、区间、子任务
   数量及最低节点数。默认监听地址为 `127.0.0.1:8888`。
2. **解析消息帧。** `protocol.py` 读取有长度限制的 P13/1 Header，并按 Header
   中指定的长度读取完整 JSON 消息体。TCP 的分包和合包不会影响应用层消息边界。
3. **验证节点身份。** `task_service.py` 要求连接上的第一条消息必须是 `AUTH`。
   `credential_store.py` 会验证节点登记信息、许可证、有效期、时间戳、一次性客户
   端随机数、可执行文件哈希白名单以及 HMAC 身份证明。
4. **建立安全会话。** 服务端与客户端派生会话密钥。客户端通过受保护的心跳证明
   在线，服务端则在 `node_registry.py` 中更新节点状态。
5. **预留子任务。** `task_state.py` 使用可重入锁保护共享任务状态。只有当前轮次
   尚未分配给该节点、且已分配节点数未达到要求时，`task_service.py` 才会为该
   节点预留任务。`task_planner.py` 负责计算该轮对应的区间。
6. **签名并发送任务。** 服务端对包含任务 ID、运算类型和区间的任务描述进行签名，
   并通过安全会话发送给客户端。
7. **验证计算结果。** 服务端检查任务 ID 和节点 ID，解析结果，并通过
   `merkle.py` 验证四步计算的 Merkle 证明。重复提交或已失效任务的结果会被拒绝。
8. **表决并合并可信结果。** 收齐要求数量的结果后，`task_service.py` 执行严格
   多数表决。如果存在严格多数结果，该可信小计会被记录，并由 `operations.py`
   按所选运算规则合并。如果不存在严格多数，服务端会记录该轮表决失败。
9. **更新信誉并完成任务。** 与多数结果一致的节点获得信誉奖励；不一致的节点
   被扣分。连续多轮提交错误结果的节点会被标记为恶意节点；
   `scheduler.py` 据此确定哪些节点仍有资格接收重要任务。最后一轮结束时，
   服务端计算并保存考核指标。
10. **等待后续任务或断开连接。** 持续连接的客户端可以在等待期间发送心跳，并
    接收后续轮次的任务。一次性客户端在结果被接受后断开连接。

## 模块说明

### 服务、配置与共享状态

| 文件 | 职责 |
| --- | --- |
| [server/server.py](./server/server.py) | 验证配置、创建 TCP 监听器、接收连接，并通过线程池分发客户端处理任务。 |
| [server/config.py](./server/config.py) | 定义监听地址、协议限制、超时、任务默认值、节点要求、许可证设置和信誉门槛。任务参数可以通过 `PROJECT13_*` 环境变量覆盖。 |
| [server/task_service.py](./server/task_service.py) | 实现认证与会话流程、任务预留、签名任务下发、结果验证、多数表决、轮次切换和错误处理。 |
| [server/task_state.py](./server/task_state.py) | 保存当前会话和轮次、节点分配情况、结果与证明、合并结果、信誉、恶意节点集合及考核数据。 |
| [server/task_planner.py](./server/task_planner.py) | 根据轮次编号，将总区间划分为平衡的闭区间子任务。 |
| [server/node_registry.py](./server/node_registry.py) | 线程安全地维护节点登录、心跳、地址、持续连接设置和任务状态。 |
| [server/operations.py](./server/operations.py) | 列出支持的区间运算，并提供子任务期望值及跨子任务的合并规则。 |

### 协议与安全

| 文件 | 职责 |
| --- | --- |
| [server/protocol.py](./server/protocol.py) | 实现 P13/1 消息帧、JSON 对象解析、大小限制、状态码和错误响应。 |
| [server/credential_store.py](./server/credential_store.py) | 生成演示用节点凭据，并验证许可证、时间、随机数、可执行文件哈希和 HMAC 字段；同时派生会话参数。 |
| [server/secure_channel.py](./server/secure_channel.py) | 使用会话 ID、消息方向、序号、随机数、密文和认证标签保护认证后的消息。 |
| [server/rsa_keys.py](./server/rsa_keys.py) | 创建并读取任务签名密钥对。私钥保存在服务端数据目录，公钥写入客户端目录。 |
| [server/signature.py](./server/signature.py) | 生成 RSA-2048/SHA-256 PKCS#1 v1.5 任务签名，并提供考核模块使用的摘要辅助函数。 |
| [server/merkle.py](./server/merkle.py) | 根据四个步骤值重新计算 Merkle 根，并检查这些步骤是否能按所选运算得到提交结果。 |
| [server/security_audit.py](./server/security_audit.py) | 将登录成功、请求拒绝和结果接受等安全事件写入独立 JSONL 文件。 |
| [server/security_tests.py](./server/security_tests.py) | 独立检查会话加密、篡改、重放、身份验证、消息帧、输入大小、可执行文件白名单、签名及不安全 C 函数调用。 |

### 调度、持久化与辅助工具

| 文件 | 职责 |
| --- | --- |
| [server/scheduler.py](./server/scheduler.py) | 选择信誉达到配置门槛且未被标记为恶意的节点，用于重要任务调度。 |
| [server/audit.py](./server/audit.py) | 将每轮结果、证明、可信值、信誉及调度信息追加写入 `data/audit.jsonl`。 |
| [server/evaluation.py](./server/evaluation.py) | 计算最终准确率、安全开销和恶意节点指标，并写入 `data/evaluation.json`。 |
| [server/provision.py](./server/provision.py) | 命令行凭据配置入口；刷新演示凭据注册表中的客户端可执行文件哈希。 |
| [server/process_manager.py](./server/process_manager.py) | 启动、停止和监控服务端子进程，也可以启动客户端可执行文件。它负责进程编排，不负责请求验证或任务执行。 |
| [server/demo.py](./server/demo.py) | 兼容旧演示入口，转而调用本文不涵盖的控制中心 GUI。 |

## 配置与运行数据

`config.py` 中的默认值为仅本机监听、区间 `1..1000`、五个子任务、每个子任务
十个节点，以及 `SUM_RANGE` 求和运算。服务端还支持 `COUNT_RANGE` 计数、
`MIN_RANGE` 最小值和 `MAX_RANGE` 最大值。`server.py` 会拒绝不支持的运算、
无效区间、每个子任务少于四个整数的配置、少于三个节点以及非正数的子任务数。

`ProcessManager` 可以通过环境变量将任务配置传入服务端。直接从命令行启动服务端
时，也可以设置相同的环境变量。运行时会生成或更新以下文件：

- `data/node_credentials.json`：演示用节点凭据注册表。
- `client/credentials/`：每个节点独立的演示凭据文件。
- `data/task_private_key.json` 和 `client/task_public.key`：任务签名密钥。
- `data/audit.jsonl`：业务及轮次审计记录。
- `data/security_audit.jsonl`：安全事件记录。
- `data/evaluation.json`：最新的考核报告。
- `data/security_tests.json`：最新的安全自检报告。

凭据和密钥文件属于运行时数据，不是源代码模块。应妥善保护任务签名私钥和节点
认证密钥。

## 启动与检查服务端

在 Windows 项目根目录中可以运行：

```powershell
.\.venv\Scripts\python.exe .\server\server.py
```

服务端会在需要时生成演示凭据和签名密钥。默认任务配置适用于本地演示；服务端
不会自动创建客户端节点。只有达到配置要求数量的不同认证节点在线，计算任务
才能完成。

可以单独运行安全自检：

```powershell
.\.venv\Scripts\python.exe .\server\security_tests.py
```

自检结果会写入 `data/security_tests.json`；只要有任一检查失败，程序就会以失败
状态退出。

## 范围与实现说明

- 任务状态和信誉保存在内存中，服务端重启后会重置。审计和报告以 JSON 或 JSONL
  文件持久保存，但不会用于恢复正在执行的任务。
- 凭据配置与可执行文件哈希白名单面向课程演示。重新编译客户端后，需要重新配置
  白名单。
- 安全信道和 RSA 操作由项目代码实现，目的是演示相关流程；在生产服务中不应将其
  视为经过审计的标准密码协议或密码库的替代品。
- 服务端使用自定义 TCP 协议，默认仅监听本机。若要部署到远程环境，需谨慎配置
  网络，并通过安全渠道分发凭据和密钥。
- 控制应用会使用 `process_manager.py`，但控制中心实现 `server/gui.py` 按要求不在
  本文说明范围内。
