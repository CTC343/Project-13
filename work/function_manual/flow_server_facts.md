# 当前服务端流程事实（供流程图使用）

仅根据当前源码只读核对；没有修改任何项目源文件。下面的“启动”是人工打开项目并点击启动，不是 Windows 开机自启动服务。

## 1. 启动、等待连接与开始任务

1. 打开 `server/gui.py` 创建控制中心，初始服务端尚未启动；点击“启动服务并等待客户端”才调用 `ProcessManager.start_server()`。控制中心自身不是 TCP 服务。依据：`server/gui.py:41–70`、`server/gui.py:127`、`server/gui.py:519–522`。
2. `start_server(task_settings=None)` 将 `PROJECT13_TASK_ENABLED` 设为 `0`，使用当前 Python 启动独立的 `server/server.py`，把标准输出、错误输出送到后台读取线程及事件队列。显式传任务设置才设为 `1`。依据：`server/process_manager.py:35–72`。
3. 服务进程先验证运算、区间、子任务数、每子任务至少四个整数、冗余节点至少 3；随后创建 IPv4 TCP 监听器，默认 `127.0.0.1:8888`。绑定/配置错误会使进程退出，不进入正常监听。依据：`server/server.py:25–30`、`server/server.py:59–89`、`server/config.py:12–28`。
4. `serve()` 创建新的共享 `TaskState`、`CredentialStore`、`NodeRegistry`；用 `select` 等连接，`accept` 后将每连接交给最多 64 个工作线程。主监听循环持续运行。连接处理结束由 `with sock` 关闭该连接。依据：`server/server.py:33–56`、`server/config.py:20`。
5. 等待模式 `TaskState.completed = not TASK_ENABLED` 因而初始为 `True`，认证节点不能领取任务，只能收到 `WAIT`、保持心跳。这个 completed 在等待模式中意为当前无任务，不宜把它画成“已有计算结果”。依据：`server/task_state.py:10–24`、`server/task_service.py:154–163`、`server/task_service.py:257–294`。
6. 用户手动打开不同节点的持续在线客户端，认证后才计入 GUI 可用节点集合。可用条件是 `persistent == "1"`、`login == "authenticated"` 且 `state != "offline"`；GUI 以节点 ID 集合去重。依据：`server/gui.py:29–38`、`server/gui.py:658–675`。
7. 用户选择求和/计数/最小值/最大值、总区间、子任务数和冗余节点数，点击运行先读并校验参数；GUI 限制范围最多 200 万个数、节点数 3–50、理论最终值在 32 位有符号范围内。若服务器未启动或可用节点不足则提示并返回，不启动任务。依据：`server/gui.py:217–284`。
8. **关键实际行为：点击运行不是向当前等待进程热下发任务。** 通过检查后，GUI 清结果和节点状态，调用 `restart_server(settings)`，先停止旧等待服务进程，再用新任务参数启动新服务进程。原连接被打断，图形客户端走自己的重连后重新认证；新进程有新的共享状态、任务水印和轮次。依据：`server/gui.py:286–291`、`server/process_manager.py:74–94`、`server/task_state.py:10–24`。图上必须画出这次重启/重新连接。

## 2. 部署凭据、登录与安全会话

9. 首次/启动凭据库会调用部署函数：确保 RSA-2048 任务签名密钥，读取已有节点注册表，缺少节点时生成随机许可证 ID 和 32 字节身份密钥；写服务端注册表和每节点 `.cred` 文件。读取已有 EXE 的 SHA-256 填白名单。显式运行 `provision.py` 以 `refresh_hashes=True` 更新编译后哈希；这是部署动作，不是客户端联网下载密钥。依据：`server/credential_store.py:46–98`、`server/rsa_keys.py:46–82`、`server/provision.py:6–8`。
10. 任务私钥保存在 `data/task_private_key.json`，公钥写 `client/task_public.key`；节点长期身份密钥用于 HMAC，任务 RSA 私钥用于任务签名，两者不要画成同一把密钥。依据：`server/rsa_keys.py:10–12`、`server/rsa_keys.py:68–81`、`server/credential_store.py:145–167`。
11. 每连接首先要求 `AUTH`；服务端解析并检查节点 ID、许可证归属、许可证到期、客户端时间戳 ±60 秒、登录 nonce 未使用、程序哈希白名单和 HMAC 身份标签；失败走错误/审计/离线。白名单为空时实际跳过哈希成员检查。依据：`server/task_service.py:225–243`、`server/credential_store.py:107–157`、`server/config.py:18`。
12. HMAC 成功后才记录已用登录 nonce，nonce 去重在锁内二次确认；去重记录保存在本进程内存，旧服务重启不保留。依据：`server/credential_store.py:94–105`、`server/credential_store.py:135–157`。
13. 服务端生成会话 ID 和服务端 nonce，用长期身份密钥及双方 nonce 派生 32 字节会话密钥；返回明文 `AUTH_OK`，其中有会话参数及 HMAC 服务端身份证明，不传输长期密钥/会话密钥本身。客户端验服务端证明后双方进入安全会话。依据：`server/credential_store.py:159–167`、`server/secure_channel.py:13–15`、`server/task_service.py:234–249`。
14. 认证后首先接收安全 `HEARTBEAT`，目前检查 `sent_at > 0`，记录心跳状态并回复安全 `HEARTBEAT_ACK`。以后业务用外层 `SECURE`、内层 `action`；发送序号、接收序号分开维护。依据：`server/task_service.py:127–151`、`server/task_service.py:251–255`、`server/secure_channel.py:104–130`。
15. 每条安全消息校验会话、严格递增序号、16 字节 nonce、HMAC 后才解密；方向、会话、序号、nonce 和密文都纳入标签。当前方案为 HMAC 派生密钥流异或，不是 TLS/AES；外层状态码未纳入标签。依据：`server/secure_channel.py:18–101`。配置中 `SESSION_TIMEOUT_SECONDS=30` 没有对应强制会话过期逻辑，不要画为每 30 秒自动换钥。

## 3. 任务分配、签名与结果验证

16. 每轮给最多 `REQUIRED_NODES` 个不同节点 ID 预留相同子任务：锁内检查未完成、当前轮比此连接上次提交轮新、节点本轮未领取、名额未满。返回 `(task_id, start, end, round_number)`；暂不能领取则进入等待/冲突分支。依据：`server/task_service.py:154–168`。
17. 任务 ID 为 `task-随机会话水印-三位轮次`；任务区间以整数除法按总轮次平衡拆分，每轮一个子区间。新轮次清空本轮结果、证明和领取集合，保留历史可信结果及信誉。依据：`server/task_state.py:26–33`、`server/task_planner.py:6–10`。
18. 无任务可领：持续节点收到 `WAIT(retry_after=2, all_complete=completed)`；随后服务端等待 `HEARTBEAT` 或 `LOGOUT`，心跳回复后再检查领取。非持续节点则 `409` 后断开。依据：`server/task_service.py:257–294`。
19. 有任务：服务端将 `task_id|operation|start|end` 用 RSA-2048/SHA-256/PKCS#1 v1.5 签名，然后通过安全消息下发 `TASK`，包含任务 ID、运算、区间和 signature；节点状态改为 computing。依据：`server/task_service.py:296–307`、`server/signature.py:18–45`。
20. 客户端完成任务后返回安全 `RESULT`；服务端核对登录节点身份与分配任务 ID，解析 value、merkle_root、proof_steps，校验四步合并值与根一致；锁内再拒绝失效任务和重复提交，保存本轮结果/证明。Merkle 只验提交内容自洽，不独立验证步骤是否真由指定区间算得。依据：`server/task_service.py:171–202`、`server/merkle.py:19–30`。
21. 尚未收满本轮节点结果时，直接返回提交层的 `ACCEPTED`；收满的最后一份结果会先在 `_store_result()` 内执行表决/轮次更新，然后才回复该节点 `ACCEPTED`。此动作表示提交通过并存入内存，不表示该节点结果已经赢得多数。依据：`server/task_service.py:204–213`、`server/task_service.py:309–319`。

## 4. 表决、信誉、审计与最终结果

22. 严格多数阈值 `len(task_results)//2 + 1`；存在多数才把该值追加为可信小计，再按当前运算合并所有已采纳子任务的小计。依据：`server/task_service.py:37–45`、`server/task_service.py:65–83`、`server/operations.py:23–34`。
23. 相同多数值节点加 5 分，错误节点减 15 分，分数限定 0–100；错误轮数累计到 5 时标记恶意（正确轮并不清零错误计数，故不是“连续五轮”）。依据：`server/task_service.py:48–62`、`server/config.py:30–34`。
24. 信誉至少 60 且不在恶意集合的节点被计算为“重要任务可用名单”；**当前领取函数没有使用此名单拦截**，不要把名单计算画成已经生效的权限门。依据：`server/task_service.py:85–96` 对比 `server/task_service.py:154–168`；`server/scheduler.py:6–14`。
25. 无严格多数：`finish_task()` 只写一条 `trusted_value=None` 的失败业务审计并返回 False，没有加可信小计、没有更新信誉。**实际调用方忽略 False，仍进入下一轮或标记全部完成**；图上若表示失败分支，必须注明当前没有自动重试/重新表决。依据：`server/task_service.py:71–76`、`server/task_service.py:204–212`。
26. 正常多数轮写 `data/audit.jsonl`：任务/轮次、节点结果、Merkle 证明、可信小计、整合值、信誉、恶意集合和考核数据。最后一轮（有多数时）先生成 `data/evaluation.json`，再写业务审计。依据：`server/task_service.py:98–123`、`server/audit.py:16–41`、`server/evaluation.py:67–94`。
27. 考核为理论答案误差、固定 Python 微基准的额外安全耗时占比、已识别恶意节点数量占配置冗余节点数的比例；安全耗时不是全链路计时。依据：`server/evaluation.py:25–85`。
28. 本轮不是最后轮：`start_next_round()` 轮次加一，持续连接重新争取下一轮任务；最后轮：`completed=True` 并打印全部完成。服务端监听进程不自动退出，持续客户端继续走 `WAIT`/心跳；GUI显示任务完成并恢复运行按钮，下一次用户运行又是重启服务。依据：`server/task_service.py:204–212`、`server/task_service.py:257–294`、`server/gui.py:624–635`、`server/gui.py:286–291`。
29. 最终合并结果输出到服务端日志并由 GUI读取展示；客户端收到的是其提交的 `ACCEPTED(task_id)` 和后续 `WAIT(all_complete)`，当前没有向全部客户端广播最终总答案的单独协议动作。依据：`server/task_service.py:78–82`、`server/task_service.py:271–274`、`server/task_service.py:313`、`server/gui.py:602–607`。

## 5. 异常、停机与独立自检

30. 每连接设置 8 秒套接字超时；协议错误、认证错误、网络错误、未预期异常分别记录安全事件。能发送时认证前明文 ERROR，安全会话建立后尽量安全 ERROR；底层断开不保证能回复。退出时释放“已领取但尚未提交”的节点名额，并将该节点标离线；外层负责关连接。依据：`server/task_service.py:225`、`server/task_service.py:325–364`、`server/server.py:49–54`。
31. 安全审计独立追加到 `data/security_audit.jsonl`，含时间、事件、节点、地址和说明；登录成功、退出、提交接受及各种拒绝/错误均有调用点。它与每轮业务审计是不同文件。依据：`server/security_audit.py:9–27`、`server/task_service.py:249`、`server/task_service.py:277–280`、`server/task_service.py:318–355`。
32. 用户点停止服务或关控制中心：管理器 terminate 服务进程，最多等待 2 秒后必要时 kill；GUI清在线节点。停止不等于保存可恢复的任务检查点，内存中的信誉/轮次等会丢失。依据：`server/process_manager.py:74–89`、`server/gui.py:524–535`、`server/gui.py:797–799`、`server/task_state.py:10–24`。
33. “安全自检”是 GUI上另一个独立入口，调用 `create_report()` 后展示结果，不是每次任务协议中的必经节点。报告包含加解密、篡改、会话重放、身份伪造、登录重放、连续帧、超长消息、EXE白名单、RSA签名、危险C函数规则扫描，共10项，保存 `data/security_tests.json`。依据：`server/gui.py:760–767`、`server/security_tests.py:169–194`。
34. 自检多数直接调用 Python函数/使用 socketpair，不启动真实业务服务，不证明当前 C 源码完整链路已跑通或无漏洞。`test_sticky_and_fragmented_frames` 当前实际发两条完整连续帧；EXE缺失时白名单检查跳过该文件，RSA自检只检查恢复编码的前后缀。依据：`server/security_tests.py:101–113`、`server/security_tests.py:130–153`。

## 建议在图中突出标记的当前边界

- 人工打开项目与启动监听；没有 Windows 开机自启动。
- 等待服务切换到计算任务会重启服务，客户端需要重连/重认证。
- `ACCEPTED` 只是提交接受；最终总结果在服务端展示，不会以单独最终结果动作广播给客户端。
- 当前程序保护是凭据/许可证与哈希白名单，任务签名不是EXE程序签名。
- 低信誉排除名单暂未进入领取任务判定。
- 无多数仍推进，暂缺自动重试/完整恢复。
- 客户端网络实现缺口由另一个客户端核对任务报告，不能用流程图掩盖。
