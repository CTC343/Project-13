"""Client-side file ownership notes for the copy-only hover enhancement."""
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def f(path, role, kind='主要实现'):
    return {'path': 'client/' + path, 'role': role, 'kind': kind}


L = f('client_logic.c', '公共客户端业务流程与阶段分支')
LH = f('client_logic.h', '公共入口、停止接口及进度回调类型', '接口声明')
GUI = f('client_gui.c', '图形窗口操作、进度显示和工作线程重连')
CLI = f('client.c', '控制台参数入口，调用公共客户端流程')
NET = f('network.c', '现有 Winsock TCP 连接、收发、超时与关闭；三个按长收发/重试接口尚缺定义', '调用协作')
NETH = f('network.h', 'TCP 接口声明；connect_retry、send_bytes、receive_exact 尚无对应定义', '接口声明')
P = f('protocol.c', 'P13/1 帧封装与解析、JSON 字段取值', '调用协作')
PH = f('protocol.h', 'P13/1 收发与 JSON 取值接口、Body 缓冲区上限', '接口声明')
SEC = f('secure_channel.c', '会话密钥派生、安全信封加解密和序号认证')
SECH = f('secure_channel.h', 'SecureSession：会话 ID、密钥、双向序号结构与接口', '接口声明')
CRYPTO = f('security.c', 'Windows BCrypt：SHA-256、HMAC、安全随机数与内存清零', '调用协作')
CRYPTOH = f('security.h', '摘要、HMAC、随机数、十六进制与清零接口', '接口声明')
CRED = f('credentials.c', '读取节点许可证凭据，定位并计算自身 EXE 哈希')
CREDH = f('credentials.h', 'NodeCredential：节点、许可证、有效期与身份密钥结构', '接口声明')
SIG = f('signature.c', '读取任务公钥并通过 BCrypt 校验 RSA 任务签名')
SIGH = f('signature.h', 'verify_task_signature 任务验签接口', '接口声明')
MERK = f('merkle.c', '四段计算、步骤结果合并和 SHA-256 Merkle 根生成')
MERKH = f('merkle.h', 'create_result_proof 结果与证明生成接口', '接口声明')
OPS = f('operations.c', '求和、计数、最小值、最大值与步骤合并')
OPSH = f('operations.h', '运算检查、计算、合并和错误演示接口', '接口声明')


data = {
    '01-overview': {
        'listen': [
            f('network.c', '客户端 TCP 连接与字节收发对端；不负责服务端监听', '调用协作'),
            NETH,
        ],
        'dispatch': [
            f('client_logic.c', '接收本轮 TASK 的客户端配合入口', '调用协作'),
            P, NET, NETH,
        ],
        'manual': [GUI, CLI, LH, f('client_logic.c', '连接按钮或控制台入口调用的 run_client 流程'), NET, NETH],
        'online': [L, CRED, SEC, CRYPTO, P, NET, NETH,
                   f('client_gui.c', '显示认证、心跳与在线等待阶段', '调用协作')],
        'reconnect': [GUI, f('client_logic.c', '断线后重新准备凭据、连接并发起完整认证'), CRED, SEC, P, NET, NETH],
        'compute': [L, SIG, MERK, OPS, CRYPTO, SEC, P, NET, NETH],
        'stay': [L, GUI, SEC, P, NET, NETH],
        'provision': [
            f('credentials.c', '客户端读取已签发的节点凭据；签发由服务端部署脚本完成', '调用协作'),
            f('signature.c', '读取部署生成的 task_public.key 公钥', '调用协作'),
        ],
    },
    '02-auth-channel': {
        'load': [CRED, CREDH, f('security.c', 'sha256_file_hex 对当前 EXE 文件计算 SHA-256', '调用协作'), L],
        'auth': [f('client_logic.c', '组装节点、许可、时间、nonce、EXE 哈希和认证标签并发送 AUTH'), CRYPTO, P, PH, NET, NETH],
        'verifyserver': [f('client_logic.c', '核对 AUTH_OK 字段、服务端 HMAC 证明并派生会话密钥'), SEC, SECH, CRYPTO,
                         f('protocol.c', '提取服务端返回的会话 ID、随机数与证明字段', '调用协作')],
        'ready': [SEC, SECH, f('client_logic.c', '持有派生会话并开始第一次安全心跳'), CRYPTO, CREDH],
        'authok': [
            f('client_logic.c', '客户端接收并核对 AUTH_OK 的消息类型、状态和必需字段', '调用协作'),
            P, NET, NETH,
        ],
        'payload': [f('client_logic.c', '组装 HEARTBEAT、RESULT、LOGOUT 等客户端业务 JSON')],
        'seq': [SEC, SECH, f('security.c', 'BCryptGenRandom 生成每条消息 nonce；提供 HMAC 与编码', '调用协作')],
        'encrypt': [SEC, SECH, CRYPTO, CRYPTOH],
        'frame': [f('client_logic.c', 'send_secure 把安全信封交给协议层'),
                  f('protocol.c', 'protocol_send_frame 生成长度 Header 并调用字节发送接口'), PH, NET, NETH],
        'envelope': [SEC, SECH, CRYPTO,
                     f('protocol.c', '从信封 JSON 提取 session_id、sequence、nonce、ciphertext、tag', '调用协作'),
                     f('client_logic.c', '要求接收到 SECURE 消息，再调用 open_server_message')],
        'decrypt': [SEC, CRYPTO,
                    f('protocol.c', '在客户端解密后用轻量字段函数读取 action 与业务字段', '调用协作'),
                    f('client_logic.c', 'receive_secure_any 校验安全消息结果并分派业务动作')],
        'business': [f('client_logic.c', '根据 WAIT、TASK、ACK、ACCEPTED 等动作进入对应处理分支'), P],
        'authfail': [
            f('client_logic.c', '客户端读取认证拒绝原因并进入本次清理', '调用协作'),
            f('client_gui.c', '普通 AUTH 拒绝通常返回 1，图形工作线程仍会按规则重试', '调用协作'),
            P, NET,
        ],
        'proofbad': [f('client_logic.c', '服务端证明或会话派生失败设置退出码 2'), SEC, CRYPTO,
                     f('client_gui.c', '工作线程收到退出码 2 后停止自动重连', '调用协作')],
        'msgbad': [SEC, CRYPTO, f('client_logic.c', '安全消息验证失败即拒收、退出本次连接并清理'), P, NET],
    },
    '03-task-compute': {
        'task': [f('client_logic.c', '客户端接收安全 TASK 并读取任务字段', '调用协作'), SEC, P, NET, NETH],
        'fields': [f('client_logic.c', '提取任务 ID、运算、起止值和签名，检查起点不大于终点'),
                   f('protocol.c', 'json_get_string / json_get_long 读取各任务字段', '调用协作'),
                   f('operations.c', 'is_operation_supported 检查四种运算代码', '调用协作'), OPSH],
        'verify': [SIG, SIGH, f('security.c', '计算任务文本 SHA-256 并转换签名与摘要字节', '调用协作'),
                   f('client_logic.c', '组装 task_id|operation|start|end 并调用验签')],
        'calc': [MERK, OPS, OPSH,
                 f('client_logic.c', '验签通过后调用 create_result_proof，接收总值和证明', '调用协作')],
        'merkle': [MERK, MERKH, f('operations.c', 'merge_step_values 按运算规则合并四步结果', '调用协作'),
                   f('security.c', 'sha256_hex 生成步骤叶子、父节点和根摘要', '调用协作'), CRYPTOH],
        'result': [f('client_logic.c', '组装 RESULT 并发送，随后等待 ACCEPTED'), SEC, SECH, P, PH, NET, NETH],
        'tamper': [f('client_logic.c', 'tamper 模式在验签前把 range_end 增加 1'),
                   f('client_gui.c', '模式下拉框选择 tamper 并传给公共流程', '调用协作'),
                   f('client.c', '控制台第二个参数可选择 tamper 模式', '调用协作'),
                   f('signature.c', '对改后的任务文本验签，预期不通过', '调用协作')],
        'bad': [f('client_logic.c', 'RSA 验签失败停止计算，设置退出码 2 并清理'), SIG,
                f('client_gui.c', '返回码 2 阻止外层工作线程继续重连', '调用协作')],
        'wrong': [f('merkle.c', '先算四段，再在合并和建根之前调用错误步骤修改'),
                  f('operations.c', 'change_step_for_wrong_test 修改第一段或第四段结果'),
                  f('client_logic.c', '从 mode=wrong 设置 simulate_wrong_result', '调用协作'),
                  f('client_gui.c', '提供 wrong 模式选项', '调用协作'),
                  f('client.c', '控制台可传入 wrong 模式参数', '调用协作')],
        'wait': [f('client_logic.c', '持续模式收到 WAIT 后等待并发送心跳；409 进入一般错误处理', '调用协作'), SEC, P, NET, NETH],
        'proof': [
            f('client_logic.c', '上传总结果、四步值和根作为服务端验证输入', '调用协作'),
            f('merkle.c', '生成提交的 proof_steps 与 merkle_root', '调用协作'),
        ],
        'invalid': [f('client_logic.c', '字段缺失、运算未知或区间无效时以一般错误码 1 清理退出'),
                    f('client_gui.c', '返回 1 时通常等待 2 秒后重连', '调用协作'), P, OPS],
    },
    '04-results': {
        'validate': [
            f('client_logic.c', 'RESULT 发送对端：提供 task_id、node_id、value、proof_steps 和根', '调用协作'),
            f('merkle.c', '服务端验证所使用的四步值与根由此生成', '调用协作'),
        ],
        'ack': [f('client_logic.c', '客户端等待 ACCEPTED 后才显示本次提交成功；不把它当最终总答案', '调用协作'),
                f('client_gui.c', '进度显示为本次任务提交完成', '调用协作'), SEC, P, NET, NETH],
        'reject': [f('client_logic.c', '处理安全 ERROR 或非 200 状态，结束本次连接', '调用协作'),
                   f('client_gui.c', '一般错误结束后按外层规则尝试重连', '调用协作'), P, SEC, NET],
    },
    '05-lifecycle': {
        'wait': [f('client_logic.c', 'WAIT 消息接收对端；读取 retry_after，不因 all_complete 自动退出', '调用协作'), SEC, P, NET, NETH],
        'heartbeat': [f('client_logic.c', '客户端 send_heartbeat 发出 sent_at 并等待 HEARTBEAT_ACK', '调用协作'),
                      SEC, P, NET, NETH],
        'sleep': [f('client_logic.c', 'WAIT 分支把等待间隔限制为 1～5 秒，然后检查停止标志'),
                  f('protocol.c', '提取 retry_after 字段', '调用协作'),
                  f('client_gui.c', '显示当前等待状态', '调用协作')],
        'sendhb': [f('client_logic.c', 'send_heartbeat 组装 HEARTBEAT，发送后要求 HEARTBEAT_ACK'),
                   SEC, SECH, P, PH, NET, NETH],
        'manualstop': [f('client_gui.c', '断开按钮或关闭窗口设置 manual_stop_requested 并请求停止'),
                       f('client_logic.c', 'request_client_stop 设置标志，持续循环退出时尝试 LOGOUT'), LH, SEC, P, NET, NETH],
        'single': [f('client.c', '默认 keep_online=0；可用 stay 参数改为持续模式', '调用协作'),
                   f('client_logic.c', '非持续模式收到 409 后结束本次连接并清理', '调用协作'), P, NET],
        'error': [f('client_logic.c', '识别协议/安全消息错误，统一跳转 cleanup', '调用协作'),
                  f('protocol.c', '报告 Header、长度或 JSON 取值相关失败', '调用协作'),
                  f('secure_channel.c', '安全信封、序号或标签不符时拒绝消息', '调用协作'), NET, NETH,
                  f('client_gui.c', '根据本轮退出码决定外层是否重连', '调用协作')],
        'exitcode': [f('client_gui.c', 'client_worker 检查人工停止或退出码 2；其他情况继续重试'),
                     f('client_logic.c', '返回 0/1/2 区分正常、一般失败与证明/任务验签阻断', '调用协作'), LH],
        'again': [f('client_gui.c', '普通中断后 Sleep(2000)，再完整调用 run_client'),
                  f('client_logic.c', '每轮重置本地会话与停止标志，重新进入连接准备', '调用协作'), NETH],
        'authagain': [f('client_logic.c', '重新读取凭据/EXE 哈希，连接并生成新 AUTH 和会话'),
                      CRED, SEC, CRYPTO, P, NET, NETH],
        'zero': [f('client_logic.c', 'cleanup 调用关闭连接、清理凭据和安全会话'),
                 f('network.c', 'closesocket 关闭套接字，WSACleanup 释放 Winsock'),
                 f('credentials.c', 'clear_node_credential 清空含身份密钥的凭据结构'),
                 f('secure_channel.c', 'clear_secure_session 清空含会话密钥的状态'),
                 f('security.c', 'clear_sensitive 使用 SecureZeroMemory 覆写敏感内存'),
                 CREDH, SECH],
        'logout': [f('client_logic.c', '客户端正常持续模式退出时发送 LOGOUT；服务端接收端在等待分支处理', '调用协作'),
                   SEC, P, NET, NETH],
        'end': [f('client_logic.c', '单次成功、人工退出或安全阻断后返回本次流程状态'),
                f('client_gui.c', '停止或重连工作线程，并恢复按钮与最终状态', '调用协作'),
                f('client.c', '控制台打印日志并以流程返回码结束', '调用协作'),
                f('network.c', '套接字关闭与 Winsock 收尾', '调用协作')],
        'stopserver': [f('client_gui.c', '服务端停止导致连接中断后，工作线程按返回码决定重连', '调用协作'),
                       f('client_logic.c', '收发失败结束本次流程并清理', '调用协作'), NET],
    },
}

all_nodes = {}
for p in sorted(WORK.glob('0*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    all_nodes[p.stem] = {n['id'] for n in d['nodes']}
paths = set()
for slug, nodes in data.items():
    assert slug in all_nodes
    for nid, entries in nodes.items():
        assert nid in all_nodes[slug], (slug,nid)
        assert len({e['path'] for e in entries}) == len(entries), (slug,nid)
        for entry in entries:
            assert (ROOT / entry['path']).is_file(), entry
            paths.add(entry['path'])

(WORK / 'hover_client_map.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Diagrams:',len(data),'nodes:',sum(len(nodes) for nodes in data.values()),'unique client files:',len(paths))
