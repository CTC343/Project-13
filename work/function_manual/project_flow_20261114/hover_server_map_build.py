"""Read-only source-to-node mapping for the server side of the hover copy."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
MAIN = '主要实现'
COLLAB = '调用协作'


def f(name, role, kind=MAIN):
    path = 'server/' + name + '.py'
    assert (ROOT / path).is_file(), path
    return {'path': path, 'role': role, 'kind': kind}


data = {
 '01-overview': {
  'power': [
   f('demo', '兼容启动入口，创建并运行控制中心'),
   f('gui', '建立控制中心窗口、按钮、状态表和事件循环'),
  ],
  'idle': [
   f('gui', '处理“启动服务并等待客户端”操作'),
   f('process_manager', '以 TASK_ENABLED=0 启动服务进程并转发日志'),
   f('server', '创建 TCP 监听器并进入连接处理循环'),
   f('task_state', '等待模式下把 completed 初始化为 True', COLLAB),
   f('config', '提供监听地址、端口和任务默认参数', COLLAB),
  ],
  'enough': [
   f('gui', '校验输入参数，并按已认证持续在线节点数决定能否启动'),
   f('node_registry', '维护认证、心跳与在线状态，输出 NODE_STATUS', COLLAB),
   f('process_manager', '读取服务端输出并将节点事件送回控制中心', COLLAB),
   f('operations', '计算参考结果，协助检查 C 整数范围', COLLAB),
   f('config', '提供节点数、区间和子任务数默认值', COLLAB),
  ],
  'restart': [
   f('gui', '在线节点足够后清空显示并请求带任务重启'),
   f('process_manager', '先停止旧进程，再把任务参数写入环境启动新进程'),
   f('server', '读取参数、验证配置并重新监听', COLLAB),
   f('config', '从 PROJECT13_* 环境变量读取任务参数', COLLAB),
  ],
  'view': [
   f('gui', '消费日志事件并刷新整合结果、节点、审计和考核表'),
   f('process_manager', '后台读取服务端输出并写事件队列', COLLAB),
   f('audit', '读取每轮业务审计记录', COLLAB),
   f('evaluation', '读取最终考核报告', COLLAB),
   f('security_audit', '读取独立安全事件日志', COLLAB),
   f('security_tests', '读取已有安全自检报告', COLLAB),
  ],
  'listen': [
   f('server', 'socket/bind/listen/accept；select 就绪检测与线程池分发'),
   f('config', '定义 HOST、PORT 和最大工作线程数', COLLAB),
   f('task_service', '接手已 accept 的 TCP 连接并进行认证和消息处理', COLLAB),
   f('protocol', '按 Header 和 Body 长度收齐 TCP 字节流，解析 P13/1 帧', COLLAB),
  ],
  'dispatch': [
   f('task_service', '在锁内检查轮次、重复领取和名额，并预留节点任务'),
   f('task_state', '保存 assigned_nodes、当前轮次与任务 ID'),
   f('task_planner', '计算当前轮次对应的平衡区间'),
   f('config', '提供每轮节点数、运算、区间和子任务数', COLLAB),
  ],
  'vote': [
   f('task_service', '接收校验结果，收齐后严格多数表决并推进轮次'),
   f('merkle', '重建 Merkle 根并检查四步值与总值一致'),
   f('operations', '按求和/计数/最小/最大规则合并可信结果'),
   f('task_state', '以共享锁保存本轮结果、证明、信誉和轮次', COLLAB),
   f('scheduler', '计算重要任务资格名单，当前尚未拦截领取', COLLAB),
   f('audit', '落盘本轮表决和结果', COLLAB),
   f('evaluation', '成功的末轮生成误差、安全开销等考核', COLLAB),
  ],
  'complete': [
   f('task_service', '末轮设置 completed 并打印全部子任务完成'),
   f('task_state', '保存完成标志及累计整合结果'),
   f('server', '任务完成后监听循环仍继续运行', COLLAB),
   f('gui', '识别完成日志，更新显示并恢复运行按钮', COLLAB),
  ],
  'manual': [
   f('process_manager', '控制中心可按用户操作打开已编译的客户端窗口', COLLAB),
   f('gui', '提供手动打开客户端的入口，不自动创建计算节点', COLLAB),
  ],
  'online': [
   f('task_service', '处理 AUTH、首次心跳、WAIT 与后续心跳循环'),
   f('credential_store', '校验许可证、时间、登录随机数和身份 HMAC'),
   f('secure_channel', '建立并校验认证后的加密安全消息'),
   f('protocol', '经 TCP 按帧收发 AUTH/SECURE 等报文', COLLAB),
   f('node_registry', '登记 authenticated、heartbeat、waiting 等状态', COLLAB),
   f('security_audit', '记录登录成功和失败等安全事件', COLLAB),
  ],
  'reconnect': [
   f('process_manager', '任务启动时停止旧服务并启动新服务，导致旧连接中断', COLLAB),
   f('server', '重新 accept 客户端连接', COLLAB),
   f('task_service', '对新连接重新执行 AUTH 和会话建立', COLLAB),
   f('credential_store', '核验新登录请求并生成新会话参数', COLLAB),
   f('protocol', '从重连后的 TCP 字节流中接收认证帧', COLLAB),
  ],
  'compute': [
   f('task_service', '下发签名 TASK，并接收客户端加密 RESULT', COLLAB),
   f('signature', '生成客户端将要验证的 RSA 任务签名', COLLAB),
   f('secure_channel', '保护服务端下发与接收的安全消息', COLLAB),
   f('protocol', '在 TCP 连接上收发任务和结果帧', COLLAB),
  ],
  'stay': [
   f('task_service', '持续模式发送 WAIT/处理心跳；单次提交成功后结束连接', COLLAB),
   f('node_registry', '维护等待、完成和离线状态', COLLAB),
   f('protocol', '收发 WAIT、心跳和退出报文', COLLAB),
  ],
  'provision': [
   f('provision', '部署入口：刷新当前 EXE 哈希白名单并签发演示凭据'),
   f('credential_store', '生成节点密钥、许可证，写服务端注册表和客户端 .cred'),
   f('rsa_keys', '首次生成 RSA-2048 密钥对，分别写服务端私钥与客户端公钥'),
   f('config', '定义演示节点数量和许可证截止日期', COLLAB),
  ],
  'files': [
   f('task_service', '更新信誉、资格和整合结果并触发报告写入'),
   f('audit', '写 data/audit.jsonl 业务审计'),
   f('evaluation', '生成并写 data/evaluation.json 考核报告'),
   f('scheduler', '按信誉和恶意集合计算资格名单', COLLAB),
   f('task_state', '保存内存中的信誉、轮次、证明与可信小计', COLLAB),
  ],
  'tests': [
   f('gui', '提供独立安全自检按钮并显示测试结果'),
   f('security_tests', '执行十项基础用例并写 security_tests.json'),
   f('secure_channel', '被测试的消息加解密与认证实现', COLLAB),
   f('credential_store', '被测试的身份认证和白名单实现', COLLAB),
   f('protocol', '被测试的帧解析与长度限制实现', COLLAB),
   f('signature', '被测试的 RSA 任务签名实现', COLLAB),
   f('rsa_keys', '读取 RSA 密钥参数供签名自检使用', COLLAB),
  ],
  'shortage': [
   f('gui', '计算缺少节点数，提示并直接返回，不启动任务'),
   f('node_registry', '提供先前由日志同步的节点在线信息', COLLAB),
  ],
 },
 '02-auth-channel': {
  'load': [
   f('credential_store', '部署阶段写出客户端将读取的节点许可证与密钥文件', COLLAB),
   f('provision', '显式部署入口，可刷新服务端程序哈希白名单', COLLAB),
  ],
  'auth': [
   f('task_service', '要求连接首帧为 AUTH，并交给凭据库认证', COLLAB),
   f('protocol', '从 TCP 字节流中解析收到的 AUTH 帧', COLLAB),
   f('credential_store', '按照同一字段顺序重算并比较身份 HMAC', COLLAB),
  ],
  'verifyserver': [
   f('credential_store', '生成 AUTH_OK 中的 server_proof，供客户端核验', COLLAB),
   f('secure_channel', '服务端使用同一公式派生会话密钥', COLLAB),
  ],
  'ready': [
   f('credential_store', '生成会话 ID、服务端 nonce 与服务端身份证明'),
   f('secure_channel', '保存会话密钥并初始化双向序号'),
   f('task_service', '认证成功后创建 SecureSession 并进入安全业务流程', COLLAB),
  ],
  'checkauth': [
   f('credential_store', '逐项验证节点、许可、有效期、±60秒时间窗、nonce、EXE 白名单及 HMAC'),
   f('secure_channel', '提供 hmac_hex 计算预期身份标签', COLLAB),
   f('config', '定义认证时间窗和部署许可证参数', COLLAB),
  ],
  'authok': [
   f('credential_store', '产生 session_id、server_nonce、server_proof 和 session_key'),
   f('task_service', '组成 AUTH_OK 并初始化安全会话'),
   f('secure_channel', '派生会话密钥并维护会话状态', COLLAB),
   f('protocol', '把 AUTH_OK 编码为 P13/1 帧经 TCP 发出', COLLAB),
  ],
  'payload': [
   f('task_service', '将 action 和任务/等待/心跳等字段组合为业务字典'),
   f('secure_channel', '把业务字典编码为紧凑 UTF-8 JSON', COLLAB),
  ],
  'seq': [
   f('secure_channel', '递增服务端发送序号、生成新 nonce，并区分 S2C/C2S'),
   f('task_service', '调用 protect_server_message 后发送安全业务消息', COLLAB),
  ],
  'encrypt': [
   f('secure_channel', '派生 HMAC 密钥流、异或加密并生成覆盖方向与信封字段的标签'),
   f('task_service', '在 _send_secure 中调用安全会话保护消息', COLLAB),
  ],
  'frame': [
   f('protocol', '编码 Header 和 JSON Body，sendall 发完整帧；按长度读齐 TCP 流'),
   f('task_service', '把安全信封作为 SECURE 帧的 Body 交给协议层'),
   f('secure_channel', '生成 frame 中使用的加密安全信封', COLLAB),
   f('config', '提供协议版本及 Header/Body 长度上限', COLLAB),
  ],
  'envelope': [
   f('secure_channel', '验证会话、严格序号、nonce 格式、方向绑定与 HMAC 标签'),
   f('task_service', '接收 SECURE 类型后交给 open_client_message'),
   f('protocol', '从 TCP 流收齐帧并解析安全信封 JSON', COLLAB),
  ],
  'decrypt': [
   f('secure_channel', '标签通过后生成密钥流解密并解析 JSON 对象'),
   f('task_service', '取出解密后的 action 和业务字段', COLLAB),
  ],
  'business': [
   f('task_service', '按 AUTH 后的状态处理 HEARTBEAT、RESULT、LOGOUT 等动作'),
   f('node_registry', '心跳与任务流程同步在线状态', COLLAB),
   f('task_state', '任务领取和结果提交读写共享业务状态', COLLAB),
  ],
  'authfail': [
   f('credential_store', '发现非法身份/许可证/随机数等时抛出认证异常'),
   f('task_service', '记录 LOGIN_REJECTED，尽量发送 401 并结束连接'),
   f('security_audit', '写入登录拒绝安全事件', COLLAB),
   f('node_registry', '把该节点更新为 rejected/offline', COLLAB),
   f('protocol', '编码并发送认证前 ERROR 帧', COLLAB),
  ],
  'proofbad': [
   f('credential_store', '正常服务端证明由此处生成；客户端检查该证明', COLLAB),
  ],
  'msgbad': [
   f('secure_channel', '检测被篡改、重放或不属于会话的安全信封'),
   f('task_service', '把校验异常转换为协议拒绝并清理连接'),
   f('security_audit', '记录 REQUEST_REJECTED 等安全事件', COLLAB),
   f('protocol', '服务端在可发送时返回 ERROR/SECURE 错误帧', COLLAB),
  ],
 },
 '03-task-compute': {
  'reserve': [
   f('task_service', '检查本轮状态、最后提交轮次、已领取节点和名额'),
   f('task_state', '锁保护 assigned_nodes，并生成当前 task_id'),
   f('task_planner', '计算该轮的 start/end 子区间'),
   f('config', '提供每轮节点上限、总区间和子任务数量', COLLAB),
  ],
  'sign': [
   f('task_service', '组织 task_id|operation|start|end 签名文本'),
   f('signature', '按 RSA-2048/SHA-256 PKCS#1 v1.5 编码并签名'),
   f('rsa_keys', '读取服务端私钥；首次部署时生成密钥对'),
   f('task_state', '用随机会话水印和轮次组成唯一任务号', COLLAB),
   f('task_planner', '提供签名文本中的子任务区间', COLLAB),
   f('config', '提供运算代码与任务 ID 前缀', COLLAB),
  ],
  'task': [
   f('task_service', '将任务字段和 RSA 签名组合为 TASK 消息'),
   f('secure_channel', '保护 TASK 并递增 S2C 序号'),
   f('protocol', '通过 TCP 发送包含任务信封的 SECURE 帧'),
   f('node_registry', '将节点状态更新为 computing', COLLAB),
  ],
  'verify': [
   f('signature', '服务端生成客户端将核验的原始任务签名', COLLAB),
   f('rsa_keys', '部署时把对应 RSA 公钥写到客户端目录', COLLAB),
  ],
  'result': [
   f('task_service', '接收 RESULT，并把业务字段交给 _store_result', COLLAB),
   f('protocol', '接收并按长度收齐 TCP 上的 SECURE 结果帧', COLLAB),
   f('secure_channel', '验证客户端安全信封并解密出结果', COLLAB),
  ],
  'wait': [
   f('task_service', '无任务时持续连接发送 WAIT；单次连接返回 409'),
   f('task_state', '提供完成状态、已领取集合和轮次信息', COLLAB),
   f('secure_channel', '保护 WAIT/错误业务消息', COLLAB),
   f('protocol', '将 WAIT 或错误封装为帧发往客户端', COLLAB),
  ],
  'proof': [
   f('task_service', '验证节点和任务归属，解析 value/merkle_root/proof_steps'),
   f('merkle', '检查四步值、总结果与 Merkle 根的一致性'),
   f('operations', '按所选运算合并四步值', COLLAB),
   f('task_state', '在锁内检查过期/重复并保存结果与证明', COLLAB),
  ],
 },
 '04-results': {
  'validate': [
   f('task_service', '核对认证身份、分配任务、结果字段与证明'),
   f('merkle', '重建 Merkle 根，检查证明与总值一致'),
   f('operations', '按指定运算合并四步值', COLLAB),
   f('protocol', '提供 403/409/422 状态码与 ProtocolError', COLLAB),
  ],
  'store': [
   f('task_service', '持锁拒绝过期/重复结果，写 task_results 和 result_proofs'),
   f('task_state', '提供 RLock、当前任务 ID 和本轮结果容器'),
  ],
  'count': [
   f('task_service', '比较已提交结果数量与 REQUIRED_NODES，决定是否表决'),
   f('task_state', '保存本轮按节点 ID 去重的 task_results'),
   f('config', '定义本轮所需节点提交数量', COLLAB),
  ],
  'majority': [
   f('task_service', 'choose_majority 计票，以提交数//2+1 作为严格多数阈值'),
   f('task_state', '提供本轮各节点的提交结果字典', COLLAB),
  ],
  'merge': [
   f('task_service', '将多数值加入可信小计并更新 integrated_result'),
   f('operations', '求和/计数相加，最小/最大分别取极值'),
   f('task_state', '保存 trusted_results 和累计整合值', COLLAB),
   f('config', '提供当前 TASK_OPERATION', COLLAB),
  ],
  'rep': [
   f('task_service', '按多数结果奖励/扣分并累计错误轮数'),
   f('scheduler', '计算信誉达标且非恶意的资格名单，尚未用于领取拦截'),
   f('task_state', '保存信誉、累计错误、恶意集合和重要任务名单'),
   f('config', '定义初始分、奖惩、恶意阈值和资格门槛', COLLAB),
  ],
  'audit': [
   f('audit', '把当前轮次、结果、证明、表决、信誉等追加至 audit.jsonl'),
   f('task_service', '在有多数和无多数分支调用 save_round'),
   f('task_state', '提供本轮与历史业务状态', COLLAB),
   f('config', '提供审计中的任务配置元数据', COLLAB),
  ],
  'eval': [
   f('evaluation', '计算准确性、安全微基准开销、恶意比例并保存 evaluation.json'),
   f('operations', '用整个任务区间计算理论标准答案', COLLAB),
   f('signature', '安全微基准中的签名与摘要开销', COLLAB),
   f('rsa_keys', '安全微基准读取 RSA 参数', COLLAB),
   f('secure_channel', '安全微基准中的加解密往返', COLLAB),
   f('merkle', '安全微基准中的根哈希计算', COLLAB),
   f('task_service', '在成功的末轮触发考核并写回状态', COLLAB),
   f('config', '提供完整区间、运算和冗余节点数', COLLAB),
  ],
  'advance': [
   f('task_service', '末轮设 completed，否则调用 start_next_round'),
   f('task_state', '轮次加一并重建本轮结果、证明和领取集合'),
   f('config', '提供 TOTAL_ROUNDS 判断是否末轮', COLLAB),
  ],
  'ack': [
   f('task_service', '结果入内存后回复 ACCEPTED，仅确认本次提交'),
   f('secure_channel', '保护 ACCEPTED 业务对象', COLLAB),
   f('protocol', '通过 TCP 发出 SECURE 确认帧', COLLAB),
   f('node_registry', '更新节点等待或完成状态', COLLAB),
   f('security_audit', '记录 RESULT_ACCEPTED 安全事件', COLLAB),
  ],
  'reject': [
   f('task_service', '拒绝任务/节点不匹配、无效证明、重复或过期提交'),
   f('merkle', '返回证明一致性检查结果', COLLAB),
   f('protocol', '提供状态码并发送错误帧', COLLAB),
   f('secure_channel', '会话建立后尽量保护错误业务消息', COLLAB),
   f('security_audit', '记录请求拒绝安全事件', COLLAB),
  ],
  'nomajor': [
   f('task_service', '没有严格多数时不采纳结果、不更新信誉，改记失败审计'),
   f('task_state', '提供本轮结果；不新增可信小计', COLLAB),
  ],
  'nullaudit': [
   f('audit', '将 trusted_value=None 序列化为 null 后追加业务审计'),
   f('task_service', '先保存失败审计再返回 False；调用方当前仍推进'),
   f('task_state', '提供失败轮次中的结果和证明', COLLAB),
  ],
 },
 '05-lifecycle': {
  'unavailable': [
   f('task_service', '检查 completed、最后提交轮次、重复领取和已占名额'),
   f('task_state', '保存决定是否能领取的共享状态'),
   f('config', '给出每轮节点名额上限', COLLAB),
  ],
  'wait': [
   f('task_service', '构造 WAIT，设置 retry_after=2 和 all_complete'),
   f('task_state', '提供 completed 状态，读取时持共享锁', COLLAB),
   f('secure_channel', '生成 WAIT 的安全信封', COLLAB),
   f('protocol', '通过 TCP 发送 SECURE 帧', COLLAB),
   f('node_registry', '将节点登记为 waiting', COLLAB),
  ],
  'heartbeat': [
   f('task_service', '检查 HEARTBEAT 和 sent_at>0，返回 HEARTBEAT_ACK'),
   f('node_registry', '更新 last_heartbeat、状态和地址'),
   f('secure_channel', '验证心跳信封并保护 ACK', COLLAB),
   f('protocol', '收齐并收发 TCP 心跳/确认帧', COLLAB),
  ],
  'retrytask': [
   f('task_service', '心跳完成后回到循环，重新尝试预留本轮任务'),
   f('task_state', '共享轮次和领取集合决定是否已经出现新任务'),
   f('task_planner', '可领取时计算当前轮次区间', COLLAB),
  ],
  'sendhb': [
   f('task_service', '服务端接收并确认客户端心跳', COLLAB),
   f('protocol', '从 TCP 字节流中读取心跳帧并发送 ACK', COLLAB),
   f('secure_channel', '校验心跳安全信封', COLLAB),
  ],
  'manualstop': [
   f('task_service', '服务端仅在等待分支处理收到的 LOGOUT', COLLAB),
  ],
  'single': [
   f('task_service', 'persistent=False 且无任务时抛出 409 冲突并结束连接'),
   f('protocol', '定义 STATUS_CONFLICT 并发送错误响应', COLLAB),
   f('security_audit', '记录对应的请求拒绝事件', COLLAB),
  ],
  'error': [
   f('task_service', '设置 8 秒超时，区分认证/协议/网络/内部异常并清理'),
   f('protocol', '发现 Header/JSON/长度错误，提供 ProtocolError 与错误响应'),
   f('secure_channel', '检测会话、序号或消息标签错误', COLLAB),
   f('security_audit', '写登录拒绝、请求拒绝、网络或内部错误事件', COLLAB),
   f('node_registry', '退出时将节点状态更新为离线', COLLAB),
  ],
  'authagain': [
   f('server', 'accept 新的 TCP 连接并提交线程池', COLLAB),
   f('task_service', '重新要求 AUTH 并创建新的 SecureSession', COLLAB),
   f('credential_store', '校验新随机数和身份标签，生成新会话参数', COLLAB),
   f('secure_channel', '派生新会话密钥并从初始序号开始', COLLAB),
   f('protocol', '收发新连接上的 AUTH/AUTH_OK 帧', COLLAB),
  ],
  'free': [
   f('task_service', 'finally 中释放尚未成功提交的领取名额并标记离线'),
   f('task_state', '以共享锁修改 assigned_nodes'),
   f('node_registry', '保存 signed_out/offline 状态'),
   f('server', '外层 with 上下文关闭已连接 TCP 套接字', COLLAB),
  ],
  'logout': [
   f('task_service', '等待分支收到 LOGOUT 后记事件并跳出处理循环'),
   f('security_audit', '追加客户端主动退出的 LOGOUT 事件'),
   f('protocol', '先从 TCP 帧解析退出报文', COLLAB),
   f('secure_channel', '核验并解密 LOGOUT 安全信封', COLLAB),
  ],
  'end': [
   f('task_service', '成功单次提交、LOGOUT 或异常后结束处理并清理状态', COLLAB),
   f('server', '连接处理函数返回后关闭本客户端套接字', COLLAB),
   f('node_registry', '保存最终离线状态', COLLAB),
  ],
  'test': [
   f('gui', '提供独立安全自检入口，执行后刷新结果表'),
   f('security_tests', '可直接运行的自检脚本与报告生成入口'),
  ],
  'cases': [
   f('security_tests', '组织十个测试函数并收集 passed/detail'),
   f('secure_channel', '被测加解密、防篡改与序号防重放'),
   f('credential_store', '被测身份伪造、登录随机数去重及 EXE 白名单'),
   f('protocol', '被测连续帧与超长 Body 拒绝'),
   f('signature', '被测 RSA 任务签名'),
   f('rsa_keys', '为签名自检提供 RSA 密钥参数', COLLAB),
  ],
  'testfile': [
   f('security_tests', '写入并读取 data/security_tests.json'),
   f('gui', '显示每项测试的名称、通过情况和说明'),
  ],
  'events': [
   f('security_audit', '线程锁保护追加 security_audit.jsonl，并提供读取接口'),
   f('task_service', '在登录、提交、退出和异常处调用安全事件记录'),
   f('gui', '刷新安全事件表并显示最近记录', COLLAB),
  ],
  'stopserver': [
   f('gui', '处理停止服务/关闭控制中心操作并清空在线显示'),
   f('process_manager', 'terminate 后等待 2 秒，必要时 kill 服务进程'),
  ],
 }
}


def main():
    node_count=0
    allfiles=set()
    for slug, mapping in data.items():
        spec=json.loads((WORK/(slug+'.json')).read_text(encoding='utf-8'))
        nodes={n['id'] for n in spec['nodes']}
        assert set(mapping)<=nodes,(slug,set(mapping)-nodes)
        for id, files in mapping.items():
            node_count+=1
            paths=[f['path'] for f in files]
            assert len(paths)==len(set(paths)),(slug,id)
            allfiles.update(paths)
    (WORK/'hover_server_map.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'nodes':node_count,'files':len(allfiles),'paths':sorted(allfiles)},ensure_ascii=False))


if __name__=='__main__':main()
