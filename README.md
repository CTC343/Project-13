# 项目13 分布式计算任务安全分发与结果审计平台

Python 服务端协调任务，Windows C 客户端计算。普通用户运行 `client_gui.exe`，填写服务端地址、端口、账户和口令。首次登录自动登记本机，账户获准后进入在线节点池。同一份客户端可部署到多台 Windows 机器。另有 `client.exe` 作为命令行联调入口，两者使用同一个服务端和计算逻辑。

## 本机部署

需要 Windows x64、64 位 Python 3.12 或以上（带 OpenSSL 3 和 Tk）、Visual Studio Build Tools 的 C++ 桌面开发组件，以及用于签发实验室证书的 OpenSSL 3 命令行程序。可使用 Git for Windows 附带的 OpenSSL。以下命令在项目根目录运行。

```powershell
python -B build.py
python -B server/provision.py init --openssl '<OpenSSL.exe 的安装路径>'
python -B server/provision.py account maintainer maintainer
python -B server/provision.py account operator operator
python -B server/provision.py account auditor auditor
python -B server/gui.py
```

账号命令通过交互式提示输入和确认口令，每个账号自行设置。若自动找不到 Visual Studio，令 `PROJECT13_VCVARS` 指向其 `VC\Auxiliary\Build\vcvars64.bat`。重新构建后，停服并重新执行 `init` 登记新客户端指纹。部署版的签名私钥、签发密钥和数据在受限的 `data/runtime` 中。

1. 用维护员登录控制中心，点「账号管理」创建 `demo-01`、`demo-02`、`demo-03`，再点「启动服务并等待客户端」。
2. 从控制中心打开客户端窗口，或直接启动 `client/output/client_gui.exe`。客户端口填 `8888`，本机地址填 `127.0.0.1`。三个计算账号各开一个窗口登录。
3. 控制中心切换到操作员，选择区间求和，设定范围 `1–1000`、子任务 `5`、每轮节点 `3`。点击运行，结果应为 `500500`。
4. 审计员可登录查看审计和安全自检。维护员可以停服。正常关闭控制中心会受控停止它启动的服务。

## 账号与窗口预览

维护员从控制中心的「账号管理」创建客户端账号，看到已有账号是在线还是离线，也能看到在线和已登记的设备数量。创建已有同名账号会被拒绝。初始化维护员、操作员和审计员时使用命令行，客户端账号可从该页面创建。

客户端登录后，勾选 **Allow window preview**。维护员在「账号管理」双击在线账号即可打开实时画面；有多台设备时，先选择节点。画面来自所选设备的 Project13 窗口，每秒最多刷新一张。取消勾选、关闭预览或设备离线后停止传图。预览复用业务端口的独立加密连接，图像留在内存中。异地客户端使用服务器可达地址和同版本客户端即可使用。

## 历史日志

「系统日志」会加载先前保存的运行日志，可以用级别和关键字搜索。服务启停、恢复、节点上线离线和任务结果保存在 `data/runtime/runtime.log`，旧文件按大小轮转。任务业务审计继续保存在 `tasks.sqlite3`，账号创建和预览启停等安全事件保存在 `security_audit.jsonl`。日志保留事件及定位用的标识，口令、令牌和画面内容不写入日志。

## 跨机器和容量

用宿主机与虚拟机的隔离网段，或两台机器的私有局域网演示。设 `PROJECT13_HOST` 为服务端可达的 IPv4，`PROJECT13_PORT` 为业务端口。证书必须包含客户端实际填写的 DNS 名或 IP，初次 `provision.py init` 用相应的 `--server-name`。首次登记使用相邻端口 `业务端口 + 1`，部署网络应同时允许两端口。将 `client/output` 下构建成品、`tls/trust.pem` 和 `task_public.key` 通过可信方式分发给客户端，服务端私钥和 CA 私钥留在服务端。

`PROJECT13_MAX_CLIENTS` 默认 64，可配 3–512。它控制同时在线的业务连接容量，容量变更后重启服务。新账号和新设备可独立登记，已有登录用户从另一台机器上线时可以获得独立的设备证书。调度仍由一个服务端协调，规模上限要结合机器资源与实测负载选取。多台独立服务可以选用不同地址和运行目录，各自协调各自的任务。

## 掉线和运维

- 服务端不可达时，客户端保持窗口，持续显示离线并按退避间隔重连。服务恢复后，有效会话会自动接回。在线心跳延续会话有效期，长时间离线导致会话过期时，窗口显示登录入口。
- 客户端退出或断电时，服务端把该节点标为离线，其他节点可以继续在线。这个客户端重新启动并登录后会恢复原节点身份，并补交原来已落盘的结果。程序异常退出的拉起逻辑在后台处理，界面使用连接状态提示。
- 每批任务使用独立任务 ID。客户端先将待发结果以 AES-GCM 原子落盘，服务端事务提交后再确认。相同任务和节点的相同结果补传只返回原确认。已过期且未接收的结果保留为 `.stale`，用于人工对账。
- `server/provision.py refresh-crl` 更新吊销列表，`revoke <节点ID>` 吊销指定设备，`rotate server --server-name <地址>` 更换服务端证书。相关命令需要 OpenSSL 位置。更新信任包后，把新公有信任包分发给客户端，并在维护窗口重启服务。客户端私有设备文件默认保存在当前 Windows 用户的 `%LOCALAPPDATA%\Project13\Devices`。
- 升级与回滚见 [部署和回滚说明](DEPLOYMENT.md)。协议行为见 [通信协议](PROTOCOL.md)。

## 验证

```powershell
python -B server/gui.py --check
python -B server/security_tests.py
python -B tests/acceptance.py --openssl '<OpenSSL.exe 的安装路径>'
```

完整联调用隔离目录和模拟账号重新构建并签发测试证书。报告位于 `work/project13-verification`。当前协议、构建和部署以此 README、DEPLOYMENT.md、PROTOCOL.md 和新联调报告为准，旧版流程图与历史审计可用于回顾。
