import ast
import json
from pathlib import Path

ROOT = Path(r'F:\project13')

# 这里只生成说明数据，不导入、不执行被说明的项目模块。
DATA = {
    'server.py': (
        '服务端启动入口：检查任务配置，创建 TCP 监听器，并用线程池处理客户端连接。',
        {
            'create_server': (
                '创建 IPv4/TCP 套接字，设置地址复用，绑定配置中的 HOST 和 PORT 后开始监听，返回监听套接字。',
                []),
            'serve': (
                '创建共享任务状态、凭据库和节点登记表；用 select 等待新连接，再把每个连接交给线程池中的 run_client 处理。该函数持续运行，不主动结束。',
                [('server_socket', '[输入／状态变化] 已完成 bind 和 listen 的 TCP 监听套接字；函数在其上等待可读事件并 accept 新连接，不是某个客户端的通信连接。')]),
            'serve.run_client': (
                'serve 内部的连接处理函数：在套接字上下文中调用 handle_client，处理结束后自动关闭该客户端连接；默认参数把本次 accept 的连接和地址固定下来。',
                [('sock', '[输入／状态变化] 本次 accept 返回的客户端通信套接字；默认取定义本函数时的 client_socket，交给 handle_client 收发消息，退出 with 时关闭。'),
                 ('address', '[输入] 与 sock 对应的客户端地址元组 (IP 字符串, 端口整数)；默认取本次 client_address，用于节点登记及日志。')]),
            'validate_settings': (
                '检查配置的运算是否支持、区间与子任务数是否合法、每个子任务是否至少可分成四段、每轮冗余节点数是否至少为 3；不符合时抛出 ValueError。配置来自模块常量，不通过参数传入。',
                []),
            'main': (
                '先验证配置，再创建监听器、输出启动信息并进入 serve 主循环；监听器在退出上下文时关闭。直接运行此文件时由模块入口调用。',
                []),
        }),
    'task_service.py': (
        '认证后业务流程：安全消息收发、任务预留、结果校验、多数表决、信誉更新和连接异常清理。',
        {
            'choose_majority': (
                '统计节点结果中每个数值的票数；返回票数达到“已提交节点数的一半再加一”的严格多数值，无严格多数时返回 None。这里只进行表决，不重新计算标准答案。',
                [('task_results', '[输入] 本轮结果字典，格式为 {节点 ID: 计算结果整数}；节点 ID 区分投票者，字典中的结果值用于统计票数。')]),
            'update_reputation': (
                '将各节点结果与多数可信值比较，按配置奖励或扣分并限制信誉在 0～100；错误时累计 wrong_rounds，累计次数恰达阈值时加入恶意集合。正确提交不会清零此前错误次数，所以当前统计的是累计错误轮数。',
                [('task_results', '[输入] 本轮 {节点 ID: 结果值} 字典；逐节点判断结果是否等于 trusted_value。'),
                 ('trusted_value', '[输入] 本轮严格多数表决选出的结果值，用作奖励或扣分的比较基准，不是本函数独立计算出的标准答案。'),
                 ('task_state', '[输入／输出] 共享 TaskState 对象；读取旧信誉，并更新 reputation_scores、wrong_rounds 和 malicious_nodes。调用方负责共享状态的并发保护。')]),
            'finish_task': (
                '对本轮结果做严格多数表决；有多数时保存可信小计、合并总结果、更新信誉和重要任务资格，最后一轮还生成考核报告，并写业务审计，返回 True。无多数时只保存失败审计并返回 False；此函数本身不决定下一轮。',
                [('task_state', '[输入／输出] 包含当前轮次、节点结果、信誉和历史可信小计的共享 TaskState；函数更新 trusted_results、integrated_result、important_task_nodes，必要时更新 evaluation_report，并将相关数据落盘。')]),
            '_send_secure': (
                '将 action 与附加字段组成业务对象，经 SecureSession 加密和认证后，以 SECURE 类型协议帧发送给客户端；发送会推进本会话的服务端发送序号。',
                [('client_socket', '[输入／状态变化] 当前客户端的已连接 TCP 套接字，作为发送目标。'),
                 ('session', '[输入／输出] 当前连接的 SecureSession，提供会话 ID、密钥和发送序号；protect_server_message 会递增其 send_sequence。'),
                 ('action', '[输入] 加密业务对象的动作名，例如 TASK、WAIT、HEARTBEAT_ACK、ACCEPTED 或 ERROR。'),
                 ('status', '[输入，可选] 外层协议帧的整数状态码，默认 STATUS_OK（200）；错误响应可以传入 401、409 等错误码。'),
                 ('**values', '[输入，可变关键字] action 以外的业务字段，如 task_id、retry_after、server_time 或 detail；这些键值被合并进同一个业务对象。')]),
            '_receive_secure': (
                '接收并验证一条安全消息，再检查解密后的 action 是否等于预期动作；相符时返回业务字典，不符则抛出 ProtocolError。',
                [('client_socket', '[输入／状态变化] 当前客户端的已连接套接字，函数从中消耗一帧消息。'),
                 ('session', '[输入／输出] 当前 SecureSession；用于验证客户端会话、序号和消息认证标签，成功接收会推进 receive_sequence。'),
                 ('expected_action', '[输入] 本步骤唯一允许的业务动作字符串，如 HEARTBEAT 或 RESULT。')]),
            '_receive_secure_any': (
                '读取一帧并要求外层类型为 SECURE，随后使用会话对象验证、解密，返回业务字典；不限制业务 action。安全信封验证的 ValueError 会转换为状态码 401 的 ProtocolError。',
                [('client_socket', '[输入／状态变化] 要读取客户端消息的已连接 TCP 套接字。'),
                 ('session', '[输入／输出] 该连接的 SecureSession，负责解密和严格序号验证；成功后接收序号增加。')]),
            '_try_reserve_task': (
                '加锁检查任务是否未结束、节点是否尚未处理本轮、是否已占用名额以及名额是否已满；满足条件时将节点加入 assigned_nodes，并返回 (任务 ID, 区间起点, 区间终点, 轮次)，否则返回 None。当前函数没有检查信誉分或恶意节点集合。',
                [('node_id', '[输入] 当前已认证节点的唯一标识，用于检查重复领取并记录其占用的本轮名额。'),
                 ('last_round', '[输入] 此连接最后一次成功提交的轮次；当前轮次必须比它大，防止同一持续连接反复领取同一轮任务。'),
                 ('task_state', '[输入／输出] 共享 TaskState；读取 completed、round_number 和 assigned_nodes，在其 lock 保护下预留名额。')]),
            '_store_result': (
                '核对结果的任务 ID 与节点身份，检查四步证明与总值、Merkle 根的一致性，并在锁内拒绝过期或重复结果；通过后写入本轮内存集合并返回结果值。收齐规定节点数时调用 finish_task，随后结束或推进轮次。证明一致性本身不证明计算正确，且当前调用方未根据 finish_task 的失败返回值停止推进。',
                [('node_id', '[输入] 从本连接认证流程得到的节点 ID；结果中的 node_id 必须与它相同，不能由结果消息自由指定提交者。'),
                 ('payload', '[输入] 解密后的 RESULT 业务字典；使用 task_id、node_id、value、merkle_root 和 proof_steps，其中 proof_steps 是四个步骤整数组成的逗号分隔字符串。'),
                 ('task_info', '[输入] 此连接预留任务时得到的四元组 (task_id, task_start, task_end, assigned_round)；本函数当前仅取第一个元素 task_id 作为任务身份基准。'),
                 ('task_state', '[输入／输出] 当前共享 TaskState；加锁写 task_results、result_proofs，并在收齐结果时更新信誉、合并结果、完成标记或下一轮状态。')]),
            'handle_client': (
                '处理一条客户端连接的完整业务生命周期：认证、会话建立、首次心跳、领取签名任务、校验提交、持续等待或退出；设置 8 秒套接字超时，捕获错误并记录安全事件、尽量回复错误，最后释放尚未提交的任务名额并将节点标为离线。连接套接字本身由外层 run_client 的 with 关闭。',
                [('client_socket', '[输入／状态变化] accept 得到的该客户端已连接 TCP 套接字；用于认证和后续安全消息的全部收发，函数会设置其超时。'),
                 ('client_address', '[输入] 客户端地址二元组 (IP, 端口)，用于生成日志及节点状态中的地址文本。'),
                 ('task_state', '[输入／输出] 各连接共享的 TaskState，包含当前轮次、占用名额、结果和信誉；业务更新通过其中的锁协调。'),
                 ('credential_store', '[输入／输出] 共用的 CredentialStore；验证身份并记录已用登录随机数，再生成本连接会话参数。'),
                 ('node_registry', '[输入／输出] 共用的 NodeRegistry；登记当前节点的认证、在线、心跳、计算、等待和离线状态。')]),
        }),
    'task_state.py': (
        '用一个共享对象保存任务会话、轮次、节点结果、信誉与完成状态，并提供任务编号和轮次切换。',
        {
            'TaskState.__init__': (
                '初始化可重入锁、随机任务会话水印、第一轮编号，以及结果、证明、信誉等容器；根据 TASK_ENABLED 设置初始 completed 状态。',
                [('self', '[输出] 正在创建的 TaskState 实例；锁和全部任务状态字段都会写入此对象，供各连接共用。')]),
            'TaskState.get_task_id': (
                '用任务前缀、当前实例的会话水印和三位十进制轮次拼成任务 ID，例如 task-会话水印-001；只读取状态，不推进轮次。',
                [('self', '[输入] 当前 TaskState；读取 session_id 和 round_number 来生成任务 ID。')]),
            'TaskState.start_next_round': (
                '将轮次加一，并清空本轮结果、结果证明及已分配节点集合；保留历史可信结果、信誉和恶意节点记录。函数内部不加锁，由调用方在持有共享锁时使用。',
                [('self', '[输入／输出] 要切换轮次的 TaskState；更新 round_number、task_results、result_proofs 和 assigned_nodes。')]),
        }),
    'task_planner.py': (
        '根据配置的总闭区间和子任务数量，计算指定轮次对应的平衡子区间。',
        {
            'get_subtask_range': (
                '通过整数除法把总闭区间均匀划分到 TOTAL_ROUNDS 轮，返回指定轮次的 (start, end) 闭区间；不同子区间长度最多相差一个数。函数本身不验证轮次范围。',
                [('round_number', '[输入] 从 1 开始的子任务轮次，正常应在 1～TOTAL_ROUNDS；用于定位该轮在总区间中的起点和终点。')]),
        }),
    'operations.py': (
        '集中登记四种区间运算，提供运算识别、中文名称、结果合并和标准结果计算。',
        {
            'is_supported': (
                '检查运算代码是否出现在 OPERATION_OPTIONS 中，返回布尔值，用于拒绝未知运算。',
                [('operation', '[输入] 待检查的运算代码字符串，支持 SUM_RANGE、COUNT_RANGE、MIN_RANGE、MAX_RANGE，比较区分大小写。')]),
            'operation_label': (
                '把已知运算代码转换成配置中的中文名称；遇到未知代码时原样返回该代码。',
                [('operation', '[输入] 运算代码字符串，如 SUM_RANGE；作为名称查找键。')]),
            'merge_values': (
                '按运算规则合并若干值：求和和计数使用相加，最小值取 min，最大值取 max；空集合返回 None，未知运算抛出 ValueError。可用于合并步骤值或多个子任务的小计。',
                [('operation', '[输入] 决定合并方式的运算代码：SUM_RANGE、COUNT_RANGE、MIN_RANGE 或 MAX_RANGE。'),
                 ('values', '[输入] 待合并的数值序列，通常为步骤值列表或历史可信子任务结果列表；不在原序列中写入结果。')]),
            'expected_result': (
                '直接计算指定闭区间的理论结果：等差数列求和、整数数量、最小端点或最大端点；未知运算抛出 ValueError，函数内部不检查 start 是否小于等于 end。',
                [('operation', '[输入] 要计算理论结果的运算代码，四种代码与 OPERATION_OPTIONS 一致。'),
                 ('start', '[输入] 整数闭区间的起点，包含在计算范围内；MIN_RANGE 时直接作为理论结果。'),
                 ('end', '[输入] 整数闭区间的终点，包含在计算范围内；MAX_RANGE 时直接作为理论结果。')]),
        }),
    'node_registry.py': (
        '线程安全地记录节点的认证、地址、在线、心跳和工作状态，并输出供控制中心读取的状态行。',
        {
            'NodeRegistry.__init__': (
                '建立节点表及互斥锁；每个节点的状态以后由 update 写入。',
                [('self', '[输出] 正在初始化的 NodeRegistry 实例；写入 _lock 和空的 _nodes 节点字典。')]),
            'NodeRegistry.update': (
                '加锁创建或更新一个节点的地址、认证状态、工作状态及最后活动时间；心跳状态会刷新心跳时间，最后输出 NODE_STATUS 行。该方法只登记状态，不自行校验身份。',
                [('self', '[输入／输出] 当前 NodeRegistry；使用 _lock 保护 _nodes 并修改指定节点记录。'),
                 ('node_id', '[输入] 节点 ID，作为 _nodes 字典键；不存在时创建该节点记录。'),
                 ('address', '[输入] 节点地址文本，通常是“IP:端口”，用于展示本次连接来源。'),
                 ('login_status', '[输入] 认证状态文本，例如 authenticated、rejected 或 signed_out。'),
                 ('state', '[输入] 工作或在线状态文本，例如 online、heartbeat、computing、waiting、completed 或 offline；等于 heartbeat 时刷新 last_heartbeat。'),
                 ('persistent', '[输入，可选] 是否持续在线等待任务；非 None 时写入 bool(persistent)，默认 None 表示保留已有值，新节点未设置时为 False。')]),
            'NodeRegistry.snapshot': (
                '在锁内复制节点表及每个节点的记录字典并返回，供调用者查看当前状态；修改返回的节点字典不会直接修改登记表。',
                [('self', '[输入] 要读取快照的 NodeRegistry；读取其 _nodes，并使用 _lock 防止复制期间记录被并发更新。')]),
        }),
    'protocol.py': (
        '定义 P13/1 帧格式、协议状态码和异常，并实现按长度收发 UTF-8 JSON 对象。',
        {
            'ProtocolError.__init__': (
                '创建携带文本说明与协议状态码的异常，供上层按错误种类回复客户端。',
                [('self', '[输出] 正在创建的 ProtocolError 异常实例；继承异常消息并保存 status 字段。'),
                 ('message', '[输入] 错误原因文本，传给 Exception 初始化；str(error) 会得到它。'),
                 ('status', '[输入，可选] 要返回的整数协议状态码；默认 STATUS_BAD_REQUEST（400），也可传 401、413 等。')]),
            '_receive_until_newline': (
                '逐字节读取协议头直到 LF，返回不含 LF 的原始 bytes，避免提前读走 Body；连接提前关闭或头部超过实现允许范围时抛出 ProtocolError。',
                [('client_socket', '[输入／状态变化] 要读取协议头的已连接 TCP 套接字；每次 recv(1)，消耗到头部结束换行。')]),
            '_receive_exact': (
                '循环接收指定字节数的消息体并返回 bytes，处理一次 recv 只到达部分数据的情况；未收足即断开时抛出 ProtocolError。',
                [('client_socket', '[输入／状态变化] 要读取消息体的已连接套接字；每次最多读取本帧尚缺的字节数。'),
                 ('body_length', '[输入] 必须接收的 Body 字节总数，来自已解析并检查过的 Header；单位为字节，不是字符。')]),
            'receive_frame': (
                '读取并解析一帧 P13/1 消息，检查版本、类型字符、Body 长度、UTF-8 和顶层 JSON 对象；返回 (message_type, status, body字典)，协议不符时抛出 ProtocolError。',
                [('client_socket', '[输入／状态变化] 当前已连接 TCP 套接字；函数消费恰好一帧的 Header 和 Body，套接字超时由调用方设置。')]),
            'send_frame': (
                '将业务对象序列化为紧凑 UTF-8 JSON，按实际字节数构造 Header，并用 sendall 发送完整帧；Body 超过上限时抛出 ProtocolError。',
                [('client_socket', '[输入／状态变化] 发送目标的已连接 TCP 套接字。'),
                 ('message_type', '[输入] Header 中的外层消息类型字符串，例如 AUTH_OK、SECURE 或 ERROR；函数发送时不另做接收端那样的字符校验。'),
                 ('status', '[输入] Header 中的整数状态码，通常 200 表示成功，其他约定值表示错误。'),
                 ('body', '[输入] 要编码成 JSON 的消息体，协议约定为字典；SECURE 帧应传加密后的信封，普通响应传对应字段字典。')]),
            'send_error': (
                '发送统一的明文 ERROR 帧，Body 只有 detail 错误说明；安全会话中的加密错误由 task_service._send_secure 处理。',
                [('client_socket', '[输入／状态变化] 接收错误响应的已连接套接字。'),
                 ('status', '[输入] 错误对应的整数协议状态码，例如 400、401 或 413。'),
                 ('detail', '[输入] 供客户端读取的错误说明，放入 JSON Body 的 detail 字段。')]),
        }),
    'secure_channel.py': (
        '派生会话密钥，以 HMAC 密钥流保护业务 JSON，并校验会话、方向、严格序号和认证标签。',
        {
            'hmac_hex': (
                '把文本按 UTF-8 编码，用指定密钥计算 HMAC-SHA256，返回 64 字符的小写十六进制认证标签。',
                [('key', '[输入] HMAC 使用的密钥原始 bytes；可为节点身份密钥或派生的会话密钥，不是密钥的十六进制文本。'),
                 ('text', '[输入] 待认证的字符串；函数内部统一编码为 UTF-8。')]),
            'derive_session_key': (
                '将客户端随机数、服务端随机数和会话 ID 按 SESSION|... 文本格式绑定，用节点身份密钥做 HMAC-SHA256，返回 32 字节会话密钥。',
                [('auth_key', '[输入] 节点长期身份认证密钥的原始 bytes，通常为 32 字节，双方须持有同一值。'),
                 ('client_nonce', '[输入] 此次 AUTH 携带的客户端随机数文本，通常为 32 个十六进制字符。'),
                 ('server_nonce', '[输入] 此次认证成功后服务端生成的随机数文本，通常为 32 个十六进制字符。'),
                 ('session_id', '[输入] 此次连接的新会话 ID 文本，通常为 24 个十六进制字符，用于区分不同会话。')]),
            '_keystream': (
                '把方向、会话、8 字节大端序号、原始随机数和 4 字节大端块计数器作为 HMAC 输入，反复生成摘要并截断，返回指定长度的密钥流，供明文／密文异或。',
                [('key', '[输入] 当前会话密钥的原始 bytes，作为生成各密钥流块的 HMAC 密钥。'),
                 ('direction', '[输入] 消息方向字符串，使用 C2S 或 S2C，并按 ASCII 编码，区分两端发送方向。'),
                 ('session_id', '[输入] 当前会话 ID 字符串，按 ASCII 编码后纳入密钥流输入。'),
                 ('sequence', '[输入] 该方向的消息序号整数，编码为 8 字节无符号大端值；正常首条为 1。'),
                 ('nonce', '[输入] 本条消息的随机数原始 bytes，正常长度为 16 字节；这里接收的是解码后的值而非十六进制文本。'),
                 ('size', '[输入] 需要生成的密钥流字节数，应等于待异或的明文或密文字节长度。')]),
            'encrypt_message': (
                '将业务字典编码为紧凑 UTF-8 JSON，生成 16 字节随机数，用派生密钥流异或加密，并计算覆盖方向、会话、序号、随机数与密文的 HMAC；返回安全信封字典。本函数不自行增加序号。',
                [('key', '[输入] 此连接派生的会话密钥原始 bytes，用于生成密钥流和认证标签。'),
                 ('direction', '[输入] 此条消息方向 C2S 或 S2C，参与加密派生与标签计算。'),
                 ('session_id', '[输入] 当前会话 ID 字符串，写入信封并参与认证。'),
                 ('sequence', '[输入] 调用方分配的本方向消息序号整数，写入信封并参与加密与认证。'),
                 ('payload', '[输入] 要保护的业务 JSON 对象，通常是含 action 的字典，如 TASK 或 RESULT 的字段集合。')]),
            'decrypt_message': (
                '解析安全信封，检查会话 ID、预期序号和随机数长度，校验 HMAC 后才解密并解析 JSON；成功返回业务字典，信封无效或明文不是 JSON 对象时抛出 ValueError。该函数不保存接收状态。',
                [('key', '[输入] 与发送方一致的会话密钥原始 bytes，用于校验标签并生成解密密钥流。'),
                 ('direction', '[输入] 接收方预期的消息方向 C2S 或 S2C；与发送时的方向不一致将导致标签验证失败。'),
                 ('expected_session', '[输入] 当前连接认可的会话 ID，必须等于信封 session_id。'),
                 ('expected_sequence', '[输入] 当前方向下一条应到达的整数序号，必须与信封 sequence 相等，用于拒绝旧消息或乱序消息。'),
                 ('envelope', '[输入] 接收到的安全信封字典，应包含 session_id、sequence、nonce、ciphertext 和 tag；nonce、ciphertext、tag 使用十六进制文本。')]),
            'SecureSession.__init__': (
                '保存会话 ID 与密钥，并将服务端发送、接收序号都初始化为 0；之后各方向首条消息使用序号 1。',
                [('self', '[输出] 正在创建的 SecureSession 对象，写入 session_id、session_key、send_sequence 和 receive_sequence。'),
                 ('session_id', '[输入] 认证成功时生成的本连接会话 ID 文本。'),
                 ('session_key', '[输入] 由双方随机数和身份密钥派生的 32 字节会话密钥，保存供后续加解密使用。')]),
            'SecureSession.protect_server_message': (
                '先将服务端发送序号加一，再按 S2C 方向调用 encrypt_message，返回要发给客户端的安全信封。',
                [('self', '[输入／输出] 当前 SecureSession，提供会话和密钥，并递增 send_sequence。'),
                 ('payload', '[输入] 本次服务端要发送的业务字典，通常含 action 及 TASK、WAIT 等动作的其他字段。')]),
            'SecureSession.open_client_message': (
                '暂时将接收序号加一，按 C2S 方向校验并解密客户端信封，返回业务字典；若 decrypt_message 抛出 ValueError，则回退本次增加的序号并继续抛出异常。',
                [('self', '[输入／输出] 当前 SecureSession，提供会话 ID、密钥及预期接收序号；成功时 receive_sequence 保持递增后的值。'),
                 ('envelope', '[输入] 从 SECURE 帧 Body 解析出的客户端安全信封字典，包含会话、序号、随机数、密文和认证标签。')]),
        }),
    'credential_store.py': (
        '生成演示节点凭据与程序哈希白名单，校验登录身份，并生成每条连接的会话参数。',
        {
            'file_sha256': (
                '以二进制分块读取文件并计算 SHA-256，返回 64 字符的小写十六进制摘要，用于客户端程序哈希白名单。',
                [('path', '[输入] 要计算摘要的 pathlib.Path 文件路径对象；函数通过 path.open("rb") 打开，不接受未经转换的普通路径字符串。')]),
            '_read_store': (
                '读取固定 STORE_FILE 中的节点凭据 JSON 并返回解析结果；文件不存在、读取失败或 JSON 无效时返回空字典。函数不检查 JSON 内部结构。',
                []),
            '_write_store': (
                '确保 data 目录存在，再将完整节点凭据表以缩进 JSON 覆盖写入固定 STORE_FILE。此文件含身份密钥，应作为机密保存。',
                [('store', '[输入] 要持久化的完整节点凭据字典，通常为 {节点 ID: 凭据记录}；记录包含 license_id、expires、auth_key 和 allowed_exe_hashes。')]),
            '_write_client_credential': (
                '为指定节点生成固定文本格式的 .cred 授权文件，写入节点 ID、许可证 ID、有效期和身份密钥；路径固定在 client/credentials 下，同名文件会覆盖。',
                [('node_id', '[输入] 要签发凭据的节点 ID，同时用作文件名和文件内 node_id 的值。'),
                 ('record', '[输入] 此节点的服务端凭据记录字典；读取 license_id、expires 和 auth_key 写入客户端文件，程序白名单不写入该文件。')]),
            'provision_demo_credentials': (
                '确保任务签名密钥存在，读取已有凭据表，为演示节点补生成随机许可证和身份密钥，并根据现有客户端 EXE 计算程序哈希；逐节点重写 .cred 文件、保存凭据表，返回登记节点总数。不会无条件更换已有节点身份密钥。',
                [('refresh_hashes', '[输入，可选] 是否刷新已有节点的 allowed_exe_hashes，默认 False；为 True 且至少找到一个客户端 EXE 时才用本次计算的哈希更新已有白名单，新节点始终使用本次哈希列表。')]),
            'CredentialStore.__init__': (
                '先补齐演示凭据，再读取节点记录，建立本进程已用登录随机数表和互斥锁。初始化具有写凭据文件的副作用，并非纯读取操作。',
                [('self', '[输出] 正在创建的 CredentialStore；初始化 records、used_nonces 和 lock，供各连接共享认证。')]),
            'CredentialStore._remove_old_nonces': (
                '剔除登记时间早于 now 减去两倍认证时间窗的登录随机数，限制去重表大小；函数内部不加锁，由 authenticate 在持锁时调用。',
                [('self', '[输入／输出] 当前 CredentialStore；用过滤后的字典替换 used_nonces，保留尚在保留期内的随机数。'),
                 ('now', '[输入] 当前 Unix 秒时间戳整数；用于计算去重记录的保留截止点，比较的是记录的接收时间。')]),
            'CredentialStore.authenticate': (
                '检查登录字段、节点登记、许可证归属与有效期、±60 秒时间窗、随机数重复、程序哈希白名单及 HMAC；成功登记随机数并返回节点身份密钥 bytes，不通过时抛出 ValueError。当前白名单为空时跳过哈希成员校验，且去重状态仅在当前进程内保存。',
                [('self', '[输入／输出] 共用的 CredentialStore；从 records 取节点凭据，使用 lock 保护 used_nonces 的清理、检查和登记。'),
                 ('request', '[输入] AUTH 消息体字典，必需字段为 node_id、license_id、timestamp、client_nonce、exe_hash、auth_tag；persistent 可选，用其真假值归一化为 0 或 1，并一并纳入 HMAC 文本。')]),
            'CredentialStore.create_session': (
                '生成随机会话 ID 和服务端随机数，用身份密钥派生会话密钥并计算服务端身份证明；返回 (session_id, server_nonce, server_proof, session_key)，不在凭据对象中登记此会话。',
                [('self', '[输入] 当前 CredentialStore 实例；为统一凭据与会话创建接口而保留，当前函数体不读取或修改实例字段。'),
                 ('auth_key', '[输入] authenticate 成功后得到的节点长期身份密钥原始 bytes，作为会话派生和服务端身份证明的 HMAC 密钥。'),
                 ('client_nonce', '[输入] 本次通过认证的客户端随机数文本；绑定到新会话的密钥和服务端证明中，避免与其他登录请求混用。')]),
        }),
}


def collect(tree, prefix=''):
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = prefix + node.name
            yield name, node
            yield from collect(node, name + '.')
        elif isinstance(node, ast.ClassDef):
            yield from collect(node, prefix + node.name + '.')
        else:
            # 嵌套函数可能处于 with/循环/条件语句块中，例如 serve.run_client。
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.stmt):
                    holder = ast.Module(body=[child], type_ignores=[])
                    yield from collect(holder, prefix)


def arg_names(node):
    args = node.args
    names = [arg.arg for arg in args.posonlyargs + args.args]
    if args.vararg:
        names.append('*' + args.vararg.arg)
    names += [arg.arg for arg in args.kwonlyargs]
    if args.kwarg:
        names.append('**' + args.kwarg.arg)
    return names


files = []
for basename, (purpose, definitions) in DATA.items():
    path = ROOT / 'server' / basename
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    found = sorted(collect(tree), key=lambda item: item[1].lineno)
    assert {name for name, _ in found} == set(definitions), basename
    functions = []
    for name, node in found:
        use, params = definitions[name]
        assert arg_names(node) == [p[0] for p in params], (basename, name, arg_names(node), params)
        signature = ('async ' if isinstance(node, ast.AsyncFunctionDef) else '') + 'def ' + node.name + '(' + ast.unparse(node.args) + ')'
        if node.returns:
            signature += ' -> ' + ast.unparse(node.returns)
        signature += ':'
        functions.append({
            'name': name,
            'signature': signature,
            'purpose': use,
            'params': [{'name': p, 'description': text} for p, text in params],
            'line': node.lineno,
        })
    files.append({'path': 'server/' + basename, 'purpose': purpose, 'functions': functions})

output = ROOT / 'work' / 'function_manual' / 'server_core.json'
output.write_text(json.dumps({'files': files}, ensure_ascii=False, indent=2), encoding='utf-8')
print('Generated', output)
print('Files:', len(files), 'Functions:', sum(len(f['functions']) for f in files), 'Parameters:', sum(len(fn['params']) for f in files for fn in f['functions']))
