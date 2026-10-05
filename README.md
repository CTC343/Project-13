# 13号项目：分布式计算任务安全分发与结果审计平台

本项目是 Python 服务端与 Windows C 客户端组成的严格 C/S 系统。网络层、安全层和业务层相互分离，代码以流程直白、便于讲解和后续增加运算模块为目标。


<img width="784" height="380" alt="image" src="https://github.com/user-attachments/assets/21398988-7937-44fc-b03c-2690fd76382b" />
这是我的vscod里的文件，下载python3.14.6和Mingw记住地址然后给ai让它写就行
## 已实现功能

- 服务端把总区间平均拆成可配置数量的子任务，并支持求和、计数、最小值、最大值。
- 每个子任务至少分配给 3 个不同节点，使用严格多数原则选择可信结果。
- 每个任务具有随机会话水印和轮次号，并使用 RSA-2048 + SHA-256/PKCS#1 v1.5 签名。
- 客户端把计算拆成 4 步，返回 SHA-256 Merkle 根和步骤证明。
- 服务端更新积分与信誉；持续错误节点在第 5 轮被识别，低信誉节点不再获得重要任务。
- 服务端使用 `select` 监听就绪连接并交给线程池并发处理；完整演示中的同一轮节点会并发登录、计算和提交。
- 使用 `P13/1 Header + JSON Body` 私有协议，按长度收包，处理 TCP 粘包/拆包并提供状态码。
- 节点凭据登录会校验许可证、程序 SHA-256 白名单、时间窗、随机数和 HMAC 身份证明。
- 认证后派生临时会话密钥；消息带随机数、方向、严格序号、密文和认证标签，可拦截篡改与重放。
- 客户端连接失败时进行三次有限重连；连接和收发均设有超时。
- 软件保护采用许可证文件绑定和可执行文件完整性白名单两种手段。
- 控制中心显示节点登录、心跳、计算、提交、离线状态和详细日志。
- 服务端不自动生成计算节点；只有用户手动打开并连接的持续在线客户端才参与任务。运行前会检查在线节点数，数量不足时提示并拒绝启动任务。
- 图形客户端完成任务后保持在线并周期发送心跳，继续等待后续轮次；连接意外中断时自动重连，只有主动断开或关闭窗口才停止连接流程。
- 图形客户端单独显示当前任务 ID、运算范围和 25%/50%/75%/100% 四段执行进度。
- 业务审计与安全事件分别保存；安全自检覆盖篡改、重放、身份伪造、非法输入等场景。
- TEE 远程证明在项目专项要求中标为选做，本版本不模拟硬件 TEE。

## 一键运行

项目目录为 `F:\project13`。

1. 用 VS Code 打开整个项目目录。
2. 按 **Ctrl+Shift+B** 运行默认任务 `Project13: Demo`。
3. 任务会编译两个 C 客户端、生成凭据和程序完整性白名单，并打开服务端控制中心。系统不会自动创建计算客户端。

图形控制中心：运行任务 `Project13: Open server UI`。

单个客户端窗口：运行任务 `Project13: Open client UI`。服务端应先以“等待客户端”模式启动。每个客户端窗口使用不同节点 ID，连接成功后才计入可用节点。

实际运行顺序：

1. 在控制中心点击“启动服务并等待客户端”。
2. 手动打开所需数量的客户端窗口，填写不同节点 ID 并连接。
3. 确认控制中心显示的“手动在线节点”数量满足要求。
4. 选择运算并点击运行。节点不足时系统只提示，不会启动任务。

控制中心包含：运行控制、结果与信誉、节点在线状态、系统日志、业务审计、项目考核、安全自检、模块状态。

## 整体流程

1. 用户在控制中心选择运算，输入起始值、最终值、子任务数和冗余节点数。
2. `task_planner.py` 平均拆分区间，`task_state.py` 生成唯一任务 ID。
3. 客户端读取节点凭据和自身程序哈希，向服务端发起认证。
4. 服务端验证许可证、程序白名单、时间窗、随机数和身份标签，双方建立加密会话。
5. 客户端持续发送心跳，服务端更新可视化在线状态；空闲节点保持“在线等待任务”。
6. 服务端签名任务水印并通过安全会话下发任务。
7. 客户端验签，从运算注册表选择函数，分四步计算并建立 Merkle Tree。
8. 服务端验证会话身份、任务归属和 Merkle 证明，再进行严格多数表决。
9. 服务端按所选运算合并可信子任务结果。
10. 服务端更新信誉、调度资格、业务审计、安全审计和考核结果。

新增同类区间运算时，只需在服务端和客户端的 `operations` 模块中增加计算和合并规则；协议、认证、调度、审计流程不需要重写。

## 模块划分

```text
project13/
├── server/
│   ├── server.py             # TCP 监听和并发线程池
│   ├── protocol.py           # P13/1 Header + JSON Body
│   ├── credential_store.py   # 凭据、许可证和程序白名单
│   ├── secure_channel.py     # 会话加密、认证和抗重放
│   ├── node_registry.py      # 登录、心跳和在线状态
│   ├── rsa_keys.py           # 首次部署生成签名密钥
│   ├── signature.py          # RSA-2048 任务签名
│   ├── task_service.py       # 认证后的业务主流程
│   ├── task_state.py         # 加锁的任务共享状态
│   ├── task_planner.py       # 区间拆解
│   ├── operations.py         # 运算注册表和合并规则
│   ├── merkle.py             # 结果证明验证
│   ├── scheduler.py          # 信誉调度
│   ├── audit.py              # 业务审计
│   ├── security_audit.py     # 安全事件审计
│   ├── security_tests.py     # 安全场景自检
│   ├── evaluation.py         # 准确性、安全开销和恶意节点指标
│   ├── process_manager.py    # 服务端和并发节点演示控制
│   └── gui.py                # 服务端控制中心
└── client/
    ├── client.c              # 控制台入口
    ├── client_gui.c          # Win32 客户端窗口
    ├── client_logic.c/.h     # 登录、持续心跳、等待和执行任务
    ├── network.c/.h          # Winsock、超时和有限重连
    ├── protocol.c/.h         # P13/1 收发和简单 JSON 取值
    ├── credentials.c/.h      # 节点许可证和程序哈希
    ├── secure_channel.c/.h   # 安全会话消息
    ├── security.c/.h         # Windows CNG SHA-256、HMAC 和安全随机数
    ├── signature.c/.h        # Windows CNG RSA 验签
    ├── operations.c/.h       # 运算分派
    └── merkle.c/.h           # 四段计算与 Merkle Tree
```

## 通信协议

消息顺序如下，认证后的消息均装入加密安全信封：

```text
AUTH -> AUTH_OK -> HEARTBEAT -> HEARTBEAT_ACK
     -> TASK -> RESULT -> ACCEPTED
```

完整字段、状态码和安全边界见 `PROTOCOL.md`。

## 手动编译

```powershell
cd F:\project13
& 'D:\DevCpp\Dev-Cpp\MinGW64\bin\gcc.exe' -std=c11 -Wall -Wextra -Wpedantic -g -O0 .\client\client.c .\client\client_logic.c .\client\network.c .\client\security.c .\client\credentials.c .\client\protocol.c .\client\secure_channel.c .\client\signature.c .\client\merkle.c .\client\operations.c -o .\client\client.exe -lws2_32 -lbcrypt
& '.\.venv\Scripts\python.exe' .\server\provision.py
& '.\.venv\Scripts\python.exe' -u .\server\server.py
```

重新编译客户端后必须再次运行 `provision.py`，使服务端程序哈希白名单与新文件一致。

## 当前边界

- 凭据签发属于部署动作。课程演示在同一台机器上生成服务端注册表和客户端节点凭据；真实跨机器部署时应通过离线安全通道分别发放。
- 安全会话使用 HMAC-SHA256 派生密钥流和 Encrypt-then-MAC。课程工程不引入第三方密码库，随机数、SHA-256、HMAC 和 RSA 验签调用系统安全能力。
- Merkle 证明当前发送四个步骤并全部验证，可继续扩展为随机抽样路径证明。
- 信誉和任务轮次保存在内存中，业务审计、安全审计和考核结果保存为 JSON 文件，暂不引入数据库。
