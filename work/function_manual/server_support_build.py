import ast
import json
from pathlib import Path

ROOT = Path('F:/project13')
OUT = ROOT / 'work/function_manual/server_support.json'

def entry(purpose, **params):
    return {'purpose': purpose, 'params': params}

DATA = {
    'audit.py': {
        'purpose': '把每轮节点结果、表决、信誉和考核状态追加到业务审计 JSONL 文件，并提供读取入口。',
        'functions': {
            'save_round': entry('读取当前轮次的任务状态，将结果、证明、可信值、整合结果、信誉及考核信息作为一条 JSON 记录追加到 data/audit.jsonl。',
                task_state='[输入] 当前 TaskState 对象；从中读取轮次、任务 ID、各节点结果与证明、整合结果、信誉、恶意节点和考核报告，不由此函数修改任务状态。',
                trusted_value='[输入] 本轮严格多数表决选出的可信子任务结果；无严格多数时调用方传入 None，审计中保存为 null。'),
            'read_rounds': entry('读取 data/audit.jsonl 并返回记录列表；文件不存在时返回空列表，无法解析为 JSON 的单独一行会被跳过。'),
        },
    },
    'config.py': {
        'purpose': '集中定义网络、协议、任务、许可证和信誉配置，并从环境变量读取可覆盖的任务参数。',
        'functions': {
            'read_int': entry('读取指定环境变量并转换为整数；环境变量不存在时使用默认值，内容无法转换成整数时也返回默认值。',
                name='[输入] 要读取的环境变量名称，例如 PROJECT13_TASK_START。',
                default_value='[输入] 环境变量不存在或整数转换失败时采用的默认整数。'),
        },
    },
    'demo.py': {
        'purpose': '兼容旧演示启动方式的脚本；直接运行时在模块顶层创建 ControlCenter 并调用 run() 打开控制中心，不自动创建客户端。当前文件没有函数定义，本手册不展开 GUI 实现。',
        'functions': {},
    },
    'evaluation.py': {
        'purpose': '计算准确性误差、固定微基准中的安全开销和恶意节点指标，并保存、读取考核报告。',
        'functions': {
            'standard_answer': entry('根据当前配置的运算类型和完整任务区间，调用 expected_result() 返回整个任务的参考答案。'),
            'slow_sum': entry('逐个累加 1 到 limit 的整数并返回总和，用作性能微基准的计算负载；limit 小于 1 时循环不执行，返回 0。',
                limit='[输入] 累加上界，包含该数；微基准中传入 2000000。'),
            'measure_security_overhead': entry('先测三次逐项累加的耗时，再测三次任务签名、公钥模幂、摘要、Merkle 根构造及会话加解密的耗时，返回额外安全耗时占计算基线耗时的百分比。它是固定 Python 微基准，不是整个 C/S 系统的端到端性能测试，公钥模幂步骤也不等于完整的签名编码校验。'),
            'create_evaluation_report': entry('将整合结果与完整区间的参考答案比较，计算误差、安全微基准开销和已识别恶意节点比例，返回包含指标及通过标记的字典；参考答案为 0 时误差字段保存绝对差。',
                task_state='[输入] 当前 TaskState 对象；此处读取 malicious_nodes 集合，以其大小除以配置的 REQUIRED_NODES 计算恶意节点比例。',
                trusted_value='[输入] 所有已采纳子任务合并后的完整任务结果；虽然参数名叫可信值，此处比较的是整体答案，而非单独一轮的小计。'),
            'save_evaluation_report': entry('将报告字典写入 data/evaluation.json；文件已存在时覆盖原报告。',
                report='[输入] 要保存的考核报告字典，通常来自 create_evaluation_report()，含运算、各项指标和通过标记。'),
            'read_evaluation_report': entry('读取 data/evaluation.json 并返回解析后的报告；文件不存在时返回空字典，其他读写或 JSON 解析异常未在此处吞掉。'),
        },
    },
    'process_manager.py': {
        'purpose': '通过独立进程启动、停止或重启服务端，并将状态和输出送入事件队列；另提供打开已有客户端窗口的入口，不包含 GUI 控件实现。',
        'functions': {
            'ProcessManager.__init__': entry('初始化进程管理器，记住事件队列和项目目录，并创建服务端进程句柄及就绪事件的初始状态。',
                self='[输入/输出] 正在初始化的 ProcessManager 实例；为它设置 event_queue、project_root、server_process 和 server_ready。',
                event_queue='[输入/输出] 接收状态事件的队列对象；后续方法通过 put() 写入 (事件类型, 内容) 二元组，例如 status、server_line、server_stopped。'),
            'ProcessManager.default_task_settings': entry('把配置中的运算、起止值、子任务数量和每个子任务节点数量组织为一个新的任务设置字典并返回。',
                self='[输入] 当前 ProcessManager 实例，用于调用该实例方法；这个方法的具体默认值来自导入的配置常量。'),
            'ProcessManager.start_server': entry('若服务端尚未运行，将任务设置转换为 PROJECT13_* 环境变量，使用当前 Python 解释器隐藏启动 server/server.py，并开后台线程转发输出。返回是否发起启动；传入 None 时使用默认参数但将任务模式设为等待客户端，显式传设置时启用任务。',
                self='[输入/输出] 当前 ProcessManager 实例；保存新进程句柄、清除就绪事件，并向事件队列写入启动状态。',
                task_settings='[输入，可选，默认 None] 任务设置字典，需含 operation、start、end、subtask_count、nodes_per_subtask；为 None 时服务端只等待客户端。当前代码以“是否为 None”决定任务是否启用，以字典真假值决定是否取默认参数。'),
            'ProcessManager.stop_server': entry('停止已运行的服务端进程：先 terminate，等待 2 秒仍未结束则 kill；随后清空进程句柄和就绪事件，并写入停止状态。未运行时仅清空句柄并提示。',
                self='[输入/输出] 当前 ProcessManager 实例；读取并结束 server_process，更新 server_ready，并把状态写入 event_queue。'),
            'ProcessManager.restart_server': entry('先停止当前服务端，再用给定任务设置启动新服务端；参数为 None 或空字典时改用默认任务设置，因此重启时会传入非 None 设置并开启任务。',
                self='[输入/输出] 当前 ProcessManager 实例；其进程句柄、就绪事件和事件队列由停止、启动流程更新。',
                task_settings='[输入] 重启后使用的任务设置字典，字段与 start_server() 相同；None 或空字典会替换为 default_task_settings() 返回的默认设置。'),
            'ProcessManager.open_client_window': entry('检查 client/client_gui.exe 是否存在；存在时启动一个客户端窗口，不存在时向事件队列提示先编译。本方法只负责启动程序，不实现窗口逻辑。',
                self='[输入/输出] 当前 ProcessManager 实例；读取 project_root 定位客户端程序，并通过 event_queue 发出提示。'),
            'ProcessManager.is_server_running': entry('检查服务端进程句柄是否存在且 poll() 尚未得到退出码，返回布尔值；只表示进程存活，不证明监听端口已就绪。',
                self='[输入] 当前 ProcessManager 实例；读取它保存的 server_process。'),
            'ProcessManager._read_server_output': entry('作为后台线程逐行读取服务端标准输出；遇到 READY: 前缀时设置就绪事件，所有输出转成 server_line 事件，输出流结束后发送 server_stopped 事件。',
                self='[输入/输出] 当前 ProcessManager 实例；读取 server_process.stdout，必要时设置 server_ready，并持续向 event_queue 写入事件。'),
        },
    },
    'provision.py': {
        'purpose': '凭据签发辅助脚本；直接运行时在模块顶层调用 provision_demo_credentials(refresh_hashes=True)，创建或更新节点凭据、刷新现有客户端程序哈希白名单并打印数量。当前文件没有函数定义。',
        'functions': {},
    },
    'rsa_keys.py': {
        'purpose': '为任务签名生成、保存及读取 RSA-2048 密钥；私钥写入 data，公钥文件写入 client。',
        'functions': {
            '_probably_prime': entry('用随机底数执行 Miller–Rabin 概率素性检查，返回候选数是否通过；它是概率判断，并非严格素数证明。',
                number='[输入] 待检查的整数；小于 2 或大于 2 的偶数会被直接判为非素数。',
                rounds='[输入，可选，默认 24] 对候选数执行随机底数测试的轮数；增加轮数可降低合数误判概率，当前代码未单独校验其取值范围。'),
            '_generate_prime': entry('不断生成指定位数的奇数候选值，要求候选值减一与公开指数 65537 互素，并通过概率素性检查，最后返回候选素数。',
                bit_count='[输入] 候选数的二进制位数；通过设置最高位和最低位保证长度及奇数属性，当前调用中为 1024。'),
            'ensure_task_signing_keys': entry('检查任务私钥和公钥文件是否存在，且私钥 JSON 是否含两个素数因子字段；满足则直接保留，否则生成两个不同的 1024 位素数组成 2048 位 RSA 模数，并写入私钥 JSON 与客户端公钥文件。现有文件分支并未完整验证公私钥是否匹配。'),
            'read_private_key': entry('先确保任务签名密钥文件存在，再解析私钥 JSON，返回五元组：(模数 n, 公开指数 e, 私有指数 d, 第一个素数 p, 第二个素数 q)，均转换为整数。'),
        },
    },
    'scheduler.py': {
        'purpose': '根据信誉门槛和恶意节点集合生成重要任务候选名单；当前领取任务流程没有调用此名单实施拦截。',
        'functions': {
            'choose_important_task_nodes': entry('筛选信誉不低于配置门槛、且不在恶意集合中的节点，按节点 ID 排序返回列表；本函数只生成名单，不分配任务，也不自行禁止节点领取任务。',
                reputation_scores='[输入] 节点 ID 到信誉分的字典；只考虑当前字典中存在的节点。',
                malicious_nodes='[输入] 已标记为恶意的节点集合；其中的节点即使信誉达标也不会进入返回名单。'),
        },
    },
    'security_audit.py': {
        'purpose': '使用写入锁将安全事件追加到独立的 security_audit.jsonl 文件，并提供逐行读取功能。',
        'functions': {
            'record_security_event': entry('生成带当前本地时间的安全事件记录，在线程锁保护下向 data/security_audit.jsonl 追加一行 JSON。',
                event='[输入] 事件类型字符串，例如 LOGIN_OK、LOGIN_REJECTED、REQUEST_REJECTED 或 RESULT_ACCEPTED。',
                node_id='[输入，可选，默认 "-"] 事件涉及的节点 ID；尚未获知节点身份时可保留占位符。',
                address='[输入，可选，默认 "-"] 对端地址文本，调用处通常拼成 IP:端口；未知时使用占位符。',
                detail='[输入，可选，默认空字符串] 补充描述，例如拒绝原因、任务 ID 或登录校验结果；直接作为日志字段保存。'),
            'read_security_events': entry('读取安全事件 JSONL 并按文件顺序返回记录列表；文件不存在时返回空列表，个别 JSON 无法解析的行会被跳过。'),
        },
    },
    'security_tests.py': {
        'purpose': '运行不依赖正在监听的业务服务端的基础安全自检，并生成 JSON 报告；覆盖范围有限，不能证明系统不存在高危漏洞。',
        'functions': {
            'check': entry('执行一个无参数测试函数：正常结束视为通过，捕获 Exception 后记录失败，返回含 name、passed 和 detail 的单项结果字典。',
                name='[输入] 测试项的展示名称，用于报告中的 name 字段。',
                function='[输入] 待执行的可调用对象，应能无参数调用；失败时通过抛出异常报告，返回值本身不会被此包装器检查。'),
            'test_encrypted_roundtrip': entry('生成随机会话密钥，将示例对象加密后再解密，检查能否还原原始对象；不一致则抛出 AssertionError。'),
            'test_tamper_rejected': entry('修改合法安全信封中密文的第一个十六进制字符，确认解密校验抛出 ValueError；若篡改后仍被接受则测试失败。'),
            'test_replay_rejected': entry('先按序号 1 接收一条安全消息，再以预期序号 2 检查同一信封，确认旧序号被拒绝；这是解密接口的序号用例，不是完整网络重放演练。'),
            'make_auth_request': entry('从节点凭据中取许可证、密钥和首个允许的程序哈希，使用当前时间、指定 nonce 和 persistent=0 构造认证请求字典；可用指定标签替代正确 HMAC，便于负向测试。',
                store='[输入] CredentialStore 对象；从 records 字典读取指定节点的 license_id、auth_key 和 allowed_exe_hashes。',
                node_id='[输入] 要构造请求的节点 ID，必须已在 store.records 中登记。',
                nonce='[输入] 放入 client_nonce 的随机数字符串；测试调用通常传入 secrets.token_hex(16)，即 32 个十六进制字符。',
                tag_override='[输入，可选，默认 None] 用于覆盖正确身份 HMAC 的标签；为非空值时直接采用它，为 None 或其他假值时自动计算正确标签。'),
            'test_identity_spoof_rejected': entry('为 node-01 构造带全零伪造 HMAC 的登录请求，确认凭据认证拒绝该请求；若成功认证则测试失败。创建 CredentialStore 时可能触发演示凭据准备。'),
            'test_auth_replay_rejected': entry('对同一份合法认证请求连续认证两次，确认第二次因 nonce 重复而被拒绝；测试复用同一个内存凭据仓库，不覆盖服务端重启后的重放行为。'),
            'test_sticky_and_fragmented_frames': entry('通过 socketpair 连续发送 ONE 和 TWO 两帧，确认 Python 接收端能分别解析。虽然名称包含 fragmented，当前函数没有主动把一帧切成多次发送，也没有测试 C 客户端。'),
            'test_oversized_body_rejected': entry('发送声明 Body 长度为 9000 的 Header，确认 Python 协议解析器在读取超限 Body 前拒绝，并使用状态码 413。'),
            'test_executable_allowlist': entry('读取 node-01 的允许程序哈希，将本地现有 client.exe 和 client_gui.exe 的 SHA-256 与其比较；文件不存在时跳过该文件。它不验证这些 EXE 是否由当前源码编译。'),
            'test_rsa_task_signature': entry('检查 RSA 模数至少 2048 位，给测试文本签名后做公开指数模幂，检查结果的 00 01 FF 前缀及 SHA-256 DigestInfo 后缀。当前用例没有逐字节验证中间全部 PKCS#1 填充，也不是 C 端验签联调。'),
            'test_no_dangerous_calls': entry('扫描 client 目录下所有 .c 文本，用正则查找 gets、strcpy、strcat、system、rand 的直接调用形式，发现匹配则失败。这是有限规则扫描，不是完整静态安全分析，也不能证明不存在内存漏洞。'),
            'create_report': entry('依次运行注册的 10 个自检，汇总通过数量和明细，加上生成时间，覆盖写入 data/security_tests.json 并返回报告字典；部分用例会读取或准备演示凭据和签名密钥。'),
            'read_security_test_report': entry('读取 data/security_tests.json 并返回解析后的报告；文件不存在时返回空字典，解析错误由调用方处理。'),
        },
    },
    'signature.py': {
        'purpose': '对任务描述生成 RSA-2048/SHA-256 PKCS#1 v1.5 签名，并提供性能微基准使用的摘要整数接口。',
        'functions': {
            'text_checksum': entry('对文本的 UTF-8 字节计算 SHA-256，将 32 字节摘要按大端转换成整数返回；用于性能考核，不是 RSA 签名函数。',
                text='[输入] 待计算摘要的字符串。'),
            'sign_task': entry('读取任务签名私钥，为文本构造 SHA-256 DigestInfo 和 PKCS#1 v1.5 填充，使用两个素数上的模幂及中国剩余定理生成签名，返回定长小写十六进制字符串；签名对象是任务描述，不是客户端 EXE。',
                task_text='[输入] 要签名的完整任务描述字符串；业务调用按 task_id|operation|start|end 拼接，各字段间用竖线分隔，客户端必须使用完全相同的文本验签。'),
        },
    },
}

files=[]
for filename, spec in DATA.items():
    path=ROOT/'server'/filename
    source=path.read_text(encoding='utf-8-sig')
    tree=ast.parse(source)
    found=[]
    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                visit(node.body, prefix+node.name+'.')
            elif isinstance(node, (ast.FunctionDef,ast.AsyncFunctionDef)):
                qualified=prefix+node.name
                info=spec['functions'][qualified]
                line=source.splitlines()[node.lineno-1].strip()
                assert line.endswith(':'), (qualified,line)
                args=node.args.posonlyargs+node.args.args
                names=[a.arg for a in args]
                if node.args.vararg: names.append(node.args.vararg.arg)
                names.extend(a.arg for a in node.args.kwonlyargs)
                if node.args.kwarg: names.append(node.args.kwarg.arg)
                assert names==list(info['params']), (qualified,names,list(info['params']))
                found.append({'name':qualified,'signature':line,'purpose':info['purpose'],'params':[{'name':name,'description':info['params'][name]} for name in names]})
                visit(node.body,qualified+'.')
    visit(tree.body)
    assert set(spec['functions'])=={f['name'] for f in found}, filename
    files.append({'path':'server/'+filename,'purpose':spec['purpose'],'functions':found})
OUT.write_text(json.dumps({'files':files},ensure_ascii=False,indent=2),encoding='utf-8')
print('Files:',len(files),'Functions:',sum(len(f['functions']) for f in files))
