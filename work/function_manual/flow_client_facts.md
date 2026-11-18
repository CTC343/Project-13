# 客户端流程事实（当前源码，只读核对）

所有行号均为本次读取时的 1-based 源码行号。下述为代码中的调用和分支，不等同于当前源码已完成跨端联调。

## 1. 启动、准备与连接

1. 控制台入口读取节点 ID、行为模式和可选 `stay`，默认 `node-1`、`normal`、单次任务，随后调用公共 `run_client`，打印日志并返回退出码。来源：`client/client.c:7-29`。
2. 图形客户端在用户点击连接后读取节点和模式（normal/wrong/tamper），创建工作线程；不是开机自动连接服务。来源：`client/client_gui.c:106-116`、`:306-337`。
3. 公共流程先清空日志、会话和凭据，检查节点 ID 的字符与长度，再读取本节点凭据文件，计算正在运行的 EXE 的 SHA-256，初始化 Winsock。任一步失败进入清理。来源：`client/client_logic.c:162-190`，ID 规则位于 `:39-47`。
4. 凭据位置为程序目录下 `credentials/<node_id>.cred`；验证文件头、读取 node_id/license_id/expires/auth_key，核对节点并把 32 字节身份密钥从十六进制转回原始字节。客户端读取有效期但不在本地判断日期；有效期由服务端认证时核对。来源：`client/credentials.c:35-94`。
5. EXE 哈希由 `GetModuleFileNameA` 定位本进程文件，再调用 `sha256_file_hex` 计算。来源：`client/credentials.c:23-32`、`:97-108`。
6. 公共流程向固定 `127.0.0.1:8888` 调用 `network_connect_retry(...,3,...)`，失败则清理。来源：`client/client_logic.c:20-22`、`:191-201`。**注意当前 network.c 缺少该函数定义，不能画成已验证可用的三次重连实现。**

## 2. 身份认证与会话建立

7. 客户端生成 16 字节安全随机数并编码成 32 字符 client_nonce，取当前 Unix 时间戳，以节点长期密钥计算 HMAC：`node_id|license_id|timestamp|client_nonce|exe_hash|persistent`。来源：`client/client_logic.c:203-215`。
8. 明文 `AUTH` 携带 node_id、license_id、timestamp、client_nonce、exe_hash、auth_tag、persistent，等候服务端响应。**身份密钥不会随 AUTH 发送。** 来源：`client/client_logic.c:216-230`。
9. 要求响应为 AUTH_OK、状态 200，并能读出 session_id、server_nonce、server_proof；否则记录拒绝原因并清理，当前一般保留退出码 1。来源：`client/client_logic.c:232-243`。
10. 客户端用自身身份密钥计算 `SERVER|session_id|client_nonce|server_nonce` 的 HMAC，与 server_proof 比较，证明服务端也持有该节点密钥；再派生会话密钥。服务端证明失败/派生失败设置退出码 2 并停止本轮。来源：`client/client_logic.c:244-258`。
11. 会话密钥由 `HMAC-SHA256(auth_key, "SESSION|client_nonce|server_nonce|session_id")` 得到 32 字节。来源：`client/secure_channel.c:60-68`。
12. 会话建立后立即发送受保护的 HEARTBEAT（sent_at），等待 HEARTBEAT_ACK，通过后进入接收任务循环。来源：`client/client_logic.c:103-113`、`:260-267`。

## 3. 认证后的通用消息保护

13. 每条客户端业务消息先递增发送序号，生成 16 字节随机 nonce，用 HMAC-SHA256 派生的密钥流与业务 JSON 字节异或，密文转为十六进制，计算覆盖 `C2S|session_id|sequence|nonce_hex|ciphertext_hex` 的 HMAC，打包为 session_id/sequence/nonce/ciphertext/tag 信封。来源：`client/secure_channel.c:20-57`、`:71-132`。
14. 安全信封再通过外层 `P13/1 SECURE 0 <body_length>\n<JSON>` 帧发送。AUTH 是认证前的普通帧；TASK、RESULT、HEARTBEAT、WAIT、LOGOUT 等 action 在认证后的密文内。来源：`client/client_logic.c:91-100`；外层封装见 `client/protocol.c:11-32`。
15. 收消息时要求外层类型 SECURE；会话 ID 必须匹配，服务器消息序号必须恰为接收序号+1，nonce/密文可解析且认证标签一致，才解密。验证成功后更新接收序号。随后解析 action，要求外层状态码为 200。来源：`client/secure_channel.c:135-175`、`client/client_logic.c:50-73`。
16. 安全信封的 HMAC 不覆盖外层 Header 的 status、message_type、body_length；不要把它画成整个 TCP 帧逐字节都已认证。根据 `client/secure_channel.c:165-168` 标签输入和 `client/protocol.c:26-32` 帧构造核对。

## 4. 等待与任务执行

17. 收到 WAIT 后读取 retry_after，合法范围 1～5 秒，其他值回退 2 秒；等待结束若未主动停止则再次发送 HEARTBEAT、等 ACK，然后继续等服务端下一条业务消息。不是客户端主动轮询领取 TASK。来源：`client/client_logic.c:269-302`。
18. 客户端虽然收到 all_complete 字段对应的 WAIT 业务，但当前分支只取 retry_after，**不会因为所有任务完成自动退出**；持续模式继续心跳等待。来源：`client/client_logic.c:278-301`。
19. 收到 TASK 后提取 task_id、operation、start、end、signature；确认支持的运算且 start≤end。字段异常或运算/范围无效均清理退出。来源：`client/client_logic.c:304-323`。
20. 任务签名文本为 `task_id|operation|start|end`。客户端从程序目录的 task_public.key 读取公钥，通过 Windows BCrypt 验证 RSA-2048/SHA-256/PKCS#1 v1.5 签名；验签失败不执行任务，设置退出码 2。来源：`client/client_logic.c:329-341`，公钥读取 `client/signature.c:11-43`，验签 `:59-112`。
21. tamper 演示在验签前把 range_end 加 1，让原始签名不再匹配，预期被阻断。来源：`client/client_logic.c:127-128`、`:324-337`。
22. 任务验签后，将闭区间按整数除法分为四段，按 operation 分别计算每段结果，再按对应规则合并整体结果。四种运算是 SUM_RANGE、COUNT_RANGE、MIN_RANGE、MAX_RANGE。来源：`client/merkle.c:39-67`、`client/operations.c:6-35`、`:38-62`。
23. 四步值分别做 SHA-256 得到叶子，两个叶子哈希文本拼接后再 SHA-256，最后两个父哈希文本拼接再哈希得到根。proof_steps 是四个整数用逗号拼成的字符串，当前发送全部步骤；不是随机抽样路径证明。来源：`client/merkle.c:10-36`、`:69-71`。
24. wrong 演示是在分段计算之后、生成整体结果和根之前故意修改步骤值，再按被改的步骤生成自洽的整体结果和证明。MIN_RANGE 修改第一段，其他运算修改第四段。**因此它通常能过证明一致性检查，要靠服务端多数表决发现与多数不一致。** 来源：`client/merkle.c:63-71`、`client/operations.c:65-71`。

## 5. 返回结果、后续轮次与退出

25. RESULT 内含 task_id、node_id、value、merkle_root、proof_steps；通过安全信封发送，随后等待 ACCEPTED。发送或确认失败进入清理。来源：`client/client_logic.c:356-367`。
26. 收到 ACCEPTED 后本地记为提交成功；**ACCEPTED 只表示服务端接受并存入本节点结果，不等于该结果已经赢得多数表决，也不包含最终整合总结果。** 客户端代码没有单独接收“最终总体计算结果”的动作。来源：`client/client_logic.c:363-379`。
27. 单次模式在提交被接受后离开任务循环并结束；持续模式继续接收 TASK 或 WAIT，不重新认证。来源：`client/client_logic.c:368-385`。
28. 用户主动断开时仅设置停止标志，客户端在下一次检查时退出，不会立即中断已经阻塞的 recv；正常持续模式退出路径尝试发送加密 LOGOUT。来源：`client/client_logic.c:28-31`、`:269`、`:295`、`:381-385`；GUI按钮/关闭入口见 `client/client_gui.c:110-115`、`:181-187`。
29. 收尾关闭套接字并执行 WSACleanup；清理 auth_text、auth_tag、expected_proof、节点凭据（含身份密钥）和会话结构（含会话密钥）。来源：`client/client_logic.c:387-402`、`client/network.c:109-115`、`client/credentials.c:111-114`、`client/secure_channel.c:183-186`。
30. GUI 外层工作线程每轮调用 `run_client(..., keep_online=1, ...)`；如果是人工停止或返回码 2 就停止重连，否则等待 2 秒，再完整执行准备、连接和认证。**单次 AUTH 被服务端拒绝通常返回 1，会进入 GUI 外层重试；服务端身份证明失败或任务验签失败返回 2，不自动重试。** 来源：`client/client_gui.c:340-357`、`client/client_logic.c:232-252`、`:331-337`。
31. GUI 的 25%/50%/75%/100% 是“收到任务／验签通过／计算完成／提交被接受”四个阶段标记，不是四段计算各完成四分之一的实时数值。来源：`client/client_gui.c:135-161`、`client/client_logic.c:339-374`。

## 6. 流程图必须保留的实现边界

- **当前调用链有缺口**：network_connect_retry、network_send_bytes、network_receive_exact 在 `client/network.h:16-26`、`:39-43` 声明并被 `client/client_logic.c:194-196`、`client/protocol.c:29-32`、`:61-62` 调用，但 `client/network.c:1-115` 没有这三个定义。图可以展示业务代码已经表达的调用流程，但不能声称当前源码已可完整编译运行。
- **收包仍有缺陷**：network_receive_line 一次 recv 可能同时拿到 Header 换行后的 Body 字节，函数只把换行改为 '\0' 并返回，额外字节没有缓存留给下一次读包。来源：`client/network.c:74-107`。
- 底层 network_connect 设置发送/接收超时 5000 毫秒，但 connect 本身没有单独超时控制。来源：`client/network.c:24-50`。
- 软件“签名”是任务签名；客户端执行文件做自算 SHA-256 后上报白名单匹配，当前没有 EXE 数字签名或硬件证明。来源：`client/client_logic.c:180-185`、`:209-222`、`:329-337`、`client/signature.c:59-112`。
