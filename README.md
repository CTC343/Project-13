# 项目13 分布式计算任务安全分发与结果审计平台

Python 服务端协调任务，Windows C 客户端计算。普通用户运行 `client_gui.exe`，填写服务端地址、端口、账户和口令。首次登录自动登记本机，账户获准后进入在线节点池。同一份客户端可部署到多台 Windows 机器。另有 `client.exe` 作为命令行联调入口，两者使用同一个服务端和计算逻辑。

## 本机部署

服务端部署和客户端构建需要 Windows x64、64 位 Python 3.12 或以上（带 OpenSSL 3 和 Tk）、Visual Studio Build Tools 的 C++ 桌面开发组件，以及 OpenSSL 3 命令行程序。首次部署时，先按下文[编译客户端并生成服务端证书](#1-编译客户端并生成服务端证书)，再[创建登录账号](#2-创建登录账号)。若构建时找不到 Visual Studio，把环境变量 `PROJECT13_VCVARS` 设为该安装目录下的 `VC\Auxiliary\Build\vcvars64.bat`。

1. 在项目根目录运行 `python -B .\server\gui.py`。用维护员登录控制中心，点「账号管理」创建 `demo-01`、`demo-02`、`demo-03`，再点「启动服务并等待客户端」。
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

以下服务器命令都在**项目根目录的 PowerShell** 里执行。`$p13OpenSsl` 示例使用 Git for Windows 附带的程序。如果你的 OpenSSL 装在其他位置，改成你的 `openssl.exe` 路径。仓库忽略 `data/runtime/`、`client/output/` 和 `releases/`。客户端的设备文件写在当前 Windows 用户目录里。

### 1. 编译客户端并生成服务端证书

首次部署时，在服务器的 PowerShell 中依次运行以下三行。

```powershell
$p13OpenSsl = 'D:\Git\mingw64\bin\openssl.exe'
python -B .\build.py
python -B .\server\provision.py init --openssl $p13OpenSsl
```

如果首次部署就要让同一局域网的电脑连接，用下面两行替换上面的 `init` 命令。运行 `ipconfig` 查到服务器的局域网 IPv4 地址后，按提示输入。

```powershell
$p13LanIp = Read-Host '输入服务器的局域网 IPv4 地址'
python -B .\server\provision.py init --openssl $p13OpenSsl --server-name localhost --server-name 127.0.0.1 --server-name $p13LanIp
```

`build.py` 把两个客户端 EXE 和 DLL 放到 `client/output/`。下表列出 `provision.py init` 生成的文件及用途。

| 生成位置 | 用途 |
| --- | --- |
| `data/runtime/issuer/ca.key`、`data/runtime/issuer/` | CA 私钥用于签证书和吊销列表。目录里还保存签发和吊销记录。 |
| `data/runtime/tls/server.key`、`data/runtime/tls/server.pem` | 服务端 TLS 私钥和证书。默认签给 `localhost` 和 `127.0.0.1`。 |
| `data/runtime/task_private_key.json` | `provision.py init` 调用 `server/rsa_keys.py` 生成的任务签名私钥。 |
| `data/runtime/accounts.sqlite3` | 账号库，初始化后可用下一节的命令创建账号。 |
| `data/runtime/tls/trust.pem`、`client/output/tls/trust.pem` | 同一份公开 CA 证书和吊销列表，用于验证服务端。 |
| `client/output/task_public.key` | 公开的任务验签公钥，与 `trust.pem` 一起发给客户端。 |

### 2. 创建登录账号

运行这三条命令，分别创建维护员、操作员、审计员。每条命令都会提示输入和确认口令。

```powershell
python -B .\server\provision.py account maintainer maintainer
python -B .\server\provision.py account operator operator
python -B .\server\provision.py account auditor auditor
```

创建客户端账号时，运行 `python -B .\server\gui.py`，用维护员登录，点「账号管理」→「创建客户端账号」。账号角色、随机盐、scrypt 口令派生值、设备登记和会话摘要都保存在 `data/runtime/accounts.sqlite3`。

### 3. 启动服务和客户端生成运行数据

- **服务端。** 运行 `python -B .\server\gui.py`，登录维护员账号，点「启动服务并等待客户端」。任务、结果和信誉保存在 `data/runtime/tasks.sqlite3`。运行日志写到 `data/runtime/runtime.log`，登录和管理操作的审计写到 `data/runtime/security_audit.jsonl`。
- **客户端。** 双击解压目录里的 `client_gui.exe`，输入服务器地址、端口、账号和口令，点「Log in and Connect」。首次登录会在 `%LOCALAPPDATA%\Project13\Devices\` 生成该设备的 `*.key`、`*.pem`、`*.identity` 和 `*.storage`，分别用于设备认证、恢复节点身份和加密待发结果。服务端把签出的设备证书保存在 `data/runtime/tls/devices/`。
- **断线结果。** 客户端收到任务并算出结果后，由 `client/outbox.c` 把待发结果加密写到 `%LOCALAPPDATA%\Project13\` 下的 `*.pending`。过期且未获确认的结果保留为 `*.stale`，供后续对账。

### 4. 生成备份

先在控制中心点「停止服务」，再运行下面的命令。终端会打印 `data/runtime/backups/` 下的备份目录。

```powershell
python -B -c "import release; print(release.backup())"
```

备份包含数据库、签发记录和私钥，保留在服务器上。若要生成本地发布目录，例如 `releases/1.2.3/`，运行 `python -B .\release.py stage 1.2.3`。运行 `python -B .\release.py activate 1.2.3` 切换到该版本，或运行 `python -B .\release.py rollback` 回到上一版本，两条命令都会在切换前备份。

### 5. 更新证书和客户端的 `trust.pem`

只需更新吊销列表时，先停止服务，再执行这两行。

```powershell
$p13OpenSsl = 'D:\Git\mingw64\bin\openssl.exe'
python -B .\server\provision.py refresh-crl --openssl $p13OpenSsl
```

已有服务端证书需要覆盖新 IP 时，先按上一步备份，再运行下面的命令。提示输入地址时，填 `ipconfig` 查到的服务器局域网 IPv4。

```powershell
$p13OpenSsl = 'D:\Git\mingw64\bin\openssl.exe'
$p13LanIp = Read-Host '输入服务器的局域网 IPv4 地址'
python -B .\server\provision.py rotate server --openssl $p13OpenSsl --server-name localhost --server-name 127.0.0.1 --server-name $p13LanIp
```

看到 `Trust bundle published` 后重启服务，把新的 `data/runtime/tls/trust.pem` 放进下载包和已发出的客户端目录，路径都是 `tls/trust.pem`。客户端重开后填写服务器实际地址。吊销列表有效期为 7 天，续期后也要同步这份文件。

## 账号与窗口预览

维护员从控制中心的「账号管理」创建客户端账号，看到已有账号是在线还是离线，也能看到在线和已登记的设备数量。创建已有同名账号会被拒绝。初始化维护员、操作员和审计员时使用命令行，客户端账号可从该页面创建。

客户端登录后，勾选 **Allow window preview**。维护员在「账号管理」双击在线账号即可打开实时画面；有多台设备时，先选择节点。画面来自所选设备的 Project13 窗口，每秒最多刷新一张。取消勾选、关闭预览或设备离线后停止传图。预览复用业务端口的独立加密连接，图像留在内存中。异地客户端使用服务器可达地址和同版本客户端即可使用。

## 历史日志

「系统日志」会加载先前保存的运行日志，可以用级别和关键字搜索。服务启停、恢复、节点上线离线和任务结果保存在 `data/runtime/runtime.log`，旧文件按大小轮转。任务业务审计继续保存在 `tasks.sqlite3`，账号创建和预览启停等安全事件保存在 `security_audit.jsonl`。日志保留事件及定位用的标识，口令、令牌和画面内容不写入日志。

## 跨机器和容量

用宿主机与虚拟机的隔离网段，或两台机器的私有局域网演示。服务端默认监听 `0.0.0.0`，即所有本机 IPv4 网卡。需要限制监听范围时，用 `PROJECT13_HOST` 指定服务器要监听的 IPv4。`PROJECT13_PORT` 设置业务端口，登记端口为业务端口加一。`0.0.0.0` 是服务器的监听设置，客户端填写服务器实际可达的地址。服务端证书要覆盖这个地址，签发命令见[首次部署](#1-编译客户端并生成服务端证书)和[更新证书](#5-更新证书和客户端的-trustpem)。

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
