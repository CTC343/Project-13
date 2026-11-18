# 项目13 分布式计算任务安全分发与结果审计平台

Python 服务端协调任务，Windows C 客户端计算。普通用户运行 `client_gui.exe`，填写服务端地址、端口、账户和口令。首次登录自动登记本机，账户获准后进入在线节点池。同一份客户端可部署到多台 Windows 机器。另有 `client.exe` 作为命令行联调入口，两者使用同一个服务端和计算逻辑。

## 本机部署

服务端部署和客户端构建需要 Windows x64、64 位 Python 3.12 或以上（带 OpenSSL 3 和 Tk）、Visual Studio Build Tools 的 C++ 桌面开发组件，以及用于签发实验室证书的 OpenSSL 3 命令行程序。可使用 Git for Windows 附带的 OpenSSL。以下命令在项目根目录运行。

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

项目已有活动发布版时，从项目根目录的 `server/gui.py` 启动会打开活动版本的控制中心，使用该版本的客户端准入名单。

## 客户端部署

客户端电脑需要 Windows x64、能访问服务器的网络，以及维护员在「账号管理」中创建的客户端账号和口令。使用编译好的客户端，接收方无需安装 Python、Visual Studio 或 OpenSSL 命令行工具。

连接本项目现有服务器时，可以直接下载 [Windows x64 客户端整合包](downloads/project13-client-windows-x64.zip)，解压后双击 `client_gui.exe`。客户端 C 源码在 [`client/`](client/)，下载包单独放在 `downloads/`。

部署自己的服务器时，从活动发布版的 `releases/<版本>/client/` 收集下列文件。未使用发布版的部署从 `client/output/` 收集。先初始化服务端，再启动活动版本的控制中心，以同步本次部署的信任文件和任务验签公钥。解压后保持表中的相对路径。

| 文件 | 用途 |
| --- | --- |
| `client_gui.exe` | 双击打开客户端界面。可选的 `client.exe` 用于命令行联调。 |
| `libssl-3.dll`、`libcrypto-3.dll` | 客户端 TLS 和加密运行库，与 EXE 同目录。 |
| `vcruntime140.dll`、`vcruntime140_1.dll` | 随构建产物提供的 C 运行库，与 EXE 同目录。 |
| `tls/trust.pem` | 服务端部署的公开 CA 证书和吊销列表，用于校验服务器。 |
| `task_public.key` | 验证服务端任务签名的公钥。 |
| `runtime-LICENSE.txt`、`openssl-LICENSE.txt` | 随整合包分发的运行库许可文件。 |

1. 解压客户端目录并双击 `client_gui.exe`。同机测试填 `127.0.0.1`，其他电脑填服务器当前可达的局域网 IPv4 地址或证书覆盖的 DNS 名。
2. 端口默认填 `8888`。客户端首次登记也需要访问相邻端口 `8889`。两端需要网络互通，服务器防火墙允许这两个 TCP 端口。
3. 填写客户端账号和口令，点「Log in and Connect」。客户端首次登录会自动生成本机设备密钥并完成登记。

换网后服务器 IP 改变时，部署者需签发覆盖新地址的服务端证书。使用原 CA 续签并保持客户端版本兼容时，接收方只需替换 `tls/trust.pem`、重开客户端并填写新地址。客户端包只包含公开信任材料和任务公钥。服务器私钥、CA 私钥、账号库和本机设备身份留在各自设备上。

## 本地生成的保密文件和运行数据

服务器的 `data/runtime/`、本地发布目录 `releases/` 及客户端用户目录里的运行数据由各端自行维护。仓库里的下载包只分发公开的 `tls/trust.pem` 和 `task_public.key`，各部署实例使用自己生成的材料。

| 本地路径 | 由哪一步生成 | 用途 |
| --- | --- | --- |
| `data/runtime/issuer/ca.key`、`tls/server.key` | `python -B server/provision.py init` 调用 OpenSSL 生成。`rotate server` 更换服务端证书和私钥。 | CA 私钥用于签发证书和吊销列表。服务端私钥用于建立 TLS 连接。旧私钥可能保存在 `issuer/retired/`。 |
| `data/runtime/issuer/`、`tls/server.pem`、`tls/devices/` | `server/provision.py` 初始化签发目录、签发服务端证书。客户端首次登录时，`server/enrollment.py` 调用签发模块登记设备。 | 保存 CA 的签发和吊销状态、服务器证书以及已签发的设备证书。 |
| `data/runtime/task_private_key.json` | `server/provision.py init` 调用 `server/rsa_keys.py` 首次生成。 | 服务端用它签名任务。对应的 `task_public.key` 可以放入客户端下载包。 |
| `data/runtime/accounts.sqlite3` | `server/accounts.py` 初始化账号库。`server/provision.py account` 或控制中心「账号管理」创建账号。 | 保存账号角色、随机盐与 scrypt 口令派生值，以及已登记设备和会话摘要。 |
| `data/runtime/tasks.sqlite3`、`runtime.log*`、`security_audit.jsonl` | `server/task_state.py`、`server/runtime_log.py`、`server/security_audit.py` 在服务运行和操作过程中写入。 | 恢复任务和信誉，保存结果、运行日志和安全审计。 |
| `data/runtime/backups/` | `python -B release.py activate <版本>` 或 `rollback` 切换版本时由 `release.py` 生成。 | 保存升级前的数据库、密钥和签发记录，供恢复和对账。 |
| `%LOCALAPPDATA%\Project13\Devices\*.key`、`*.pem`、`*.identity`、`*.storage` | 每台客户端首次登录时由 `client/device.c` 创建或保存，设备证书由服务器签发。 | 用于客户端双向 TLS 身份校验、节点身份恢复和本地结果加密。每台客户端用自己的设备文件。 |
| `%LOCALAPPDATA%\Project13\*.pending`、`*.stale` | 客户端计算完成后，由 `client/outbox.c` 保存到磁盘。 | 使用设备的本地密钥加密待发和过期结果，支持断线补报和对账。 |

公开信任包由 `server/provision.py init`、`rotate server` 或 `refresh-crl` 生成。吊销列表的有效期为 7 天。维护员更新吊销列表后需要同步更新下载包里的 `tls/trust.pem`。已下载的客户端也可直接替换该文件。

## 账号与窗口预览

维护员从控制中心的「账号管理」创建客户端账号，看到已有账号是在线还是离线，也能看到在线和已登记的设备数量。创建已有同名账号会被拒绝。初始化维护员、操作员和审计员时使用命令行，客户端账号可从该页面创建。

客户端登录后，勾选 **Allow window preview**。维护员在「账号管理」双击在线账号即可打开实时画面；有多台设备时，先选择节点。画面来自所选设备的 Project13 窗口，每秒最多刷新一张。取消勾选、关闭预览或设备离线后停止传图。预览复用业务端口的独立加密连接，图像留在内存中。异地客户端使用服务器可达地址和同版本客户端即可使用。

## 历史日志

「系统日志」会加载先前保存的运行日志，可以用级别和关键字搜索。服务启停、恢复、节点上线离线和任务结果保存在 `data/runtime/runtime.log`，旧文件按大小轮转。任务业务审计继续保存在 `tasks.sqlite3`，账号创建和预览启停等安全事件保存在 `security_audit.jsonl`。日志保留事件及定位用的标识，口令、令牌和画面内容不写入日志。

## 跨机器和容量

用宿主机与虚拟机的隔离网段，或两台机器的私有局域网演示。服务端默认监听 `0.0.0.0`，即所有本机 IPv4 网卡。需要限制监听范围时，用 `PROJECT13_HOST` 指定服务器要监听的 IPv4。`PROJECT13_PORT` 设置业务端口，登记端口为业务端口加一。`0.0.0.0` 是服务器的监听设置，客户端填写服务器实际可达的地址。首次部署时，用 `provision.py init --server-name <地址>` 为该地址签发证书。需要同时支持本机和局域网登录时，可以多次传入 `--server-name`，分别列出 `localhost`、`127.0.0.1` 和局域网地址。

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
```

现场验收步骤见 [部署和回滚说明](DEPLOYMENT.md#现场验收)。
