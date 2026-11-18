import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
DEST = WORK / '交付文件'
DEST.mkdir(exist_ok=True)
source_index = json.loads((WORK.parent / 'flow_source_index.json').read_text(encoding='utf-8'))


def ref(path, func=None):
    if path.endswith('.py') and func:
        return source_index[path + ':' + func]
    if func:
        text = (ROOT / path).read_text(encoding='utf-8-sig')
        pat = re.compile(r'^(?:static\s+)?(?:int|void|long|SOCKET|DWORD|LRESULT|unsigned\s+long)(?:\s+WINAPI|\s+CALLBACK)?\s+(\w+)\s*\([^;{}]*?\)\s*\{', re.M)
        matches = list(pat.finditer(text))
        for i, match in enumerate(matches):
            if match[1] == func:
                return {'path': path, 'line': text[:match.start()].count('\n') + 1,
                        'end_line': text[:matches[i+1].start()].count('\n') if i+1 < len(matches) else len(text.splitlines())}
        raise ValueError((path, func))
    return {'path': path}


def node(id, lane, col, label, sub, sources, type='backend', icon=None, tag=None):
    n = {'id': id, 'lane': lane, 'col': col, 'type': type, 'label': label,
         'sublabel': sub, 'sources': [ref(*s) if isinstance(s, tuple) else ref(s) for s in sources]}
    if icon: n['icon'] = icon
    if tag: n['tag'] = tag
    return n


def edge(a, b, label=None, variant='default', role=None, **opts):
    e={'id': a+'--'+b, 'from': a, 'to': b, 'variant': variant, **opts}
    if label: e['label']=label
    if role: e['role']=role
    return e


def diagram(slug, title, lanes, nodes, edges, cards, main=None):
    out=(DEST / (slug+'.html')).relative_to(ROOT).as_posix()
    obj={'schema_version':2,'diagram_type':'workflow',
         'meta':{'title':title,'locale':'zh-CN','quality_profile':'showcase','output':out,
                 'repository':{'url':'https://github.com/CTC343/Project-13.git',
                               'revision':'faddfa60ce6cc578b5b2d7025ee0bf7413e15308','link_mode':'local-only'}},
         'lanes':[{'id':i,'label':label,**({'variant':'exception'} if exc else {})} for i,label,exc in lanes],
         'nodes':nodes,'edges':edges,
         'cards':[{'dot':dot,'title':heading,'items':items} for dot,heading,items in cards]}
    if main: obj['mainPath']=main
    (WORK / (slug+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


G='server/gui.py'; P='server/process_manager.py'; S='server/server.py'; T='server/task_service.py'
C='client/client_logic.c'; CG='client/client_gui.c'; A='server/credential_store.py'
SC='server/secure_channel.py'

diagram('01-overview','项目 13 · 从启动到任务完成',[
 ('control','人工操作与控制中心',False),('server','Python 服务端',False),
 ('client','Windows C 客户端（多个节点并发）',False),('records','文件、审计与独立检查',False),
 ('reject','启动限制',True)], [
 node('power','control',0,'开机后手动打开','没有开机自动运行配置',[('server/demo.py',None),(G,'run')],type='external',icon='start'),
 node('idle','control',1,'启动等待服务','先监听，不立即执行任务',[(G,'_start_server'),(P,'start_server')],type='frontend'),
 node('enough','control',2,'在线节点足够？','设置运算、区间与冗余数',[(G,'_run_operation'),(G,'_read_operation_settings')],type='security',icon='decision'),
 node('restart','control',3,'重启为任务模式','参数通过环境变量传入',[(P,'restart_server'),(P,'start_server'),(G,'_run_operation')],type='frontend'),
 node('view','control',5,'查看结果与记录','控制中心刷新状态和报告',[(G,'_read_events'),(G,'_refresh_evaluation'),(G,'_refresh_audit')],type='frontend'),
 node('listen','server',1,'监听并接入连接','127.0.0.1:8888 / 线程池',[(S,'create_server'),(S,'serve')],type='messagebus'),
 node('dispatch','server',3,'重新认证并分配','唯一任务号 / 不同节点',[(T,'handle_client'),(T,'_try_reserve_task')]),
 node('vote','server',4,'校验、表决、推进','每轮等待规定节点提交',[(T,'_store_result'),(T,'finish_task')]),
 node('complete','server',5,'全部子任务结束','保留结果，持续服务仍监听',[(T,'_store_result'),(S,'serve')],icon='success'),
 node('manual','client',1,'手动打开不同节点','输入节点 ID 后连接',[(CG,'run_selected_mode'),('client/client.c','main')],type='external'),
 node('online','client',2,'认证后心跳等待','持续客户端等待任务',[(C,'run_client')],type='security'),
 node('reconnect','client',3,'重连并再次认证','旧服务停止导致连接中断',[(CG,'client_worker'),(C,'run_client')],type='messagebus'),
 node('compute','client',4,'验签、计算、回传','四段计算与 Merkle 证明',[(C,'run_client'),('client/merkle.c','create_result_proof')],type='security'),
 node('stay','client',5,'等待后续任务或退出','持续模式与单次模式不同',[(C,'run_client')],icon='waiting'),
 node('provision','records',0,'部署时签发材料','RSA 密钥 / 凭据 / 程序白名单',[(A,'provision_demo_credentials'),('server/rsa_keys.py','ensure_task_signing_keys')],type='database'),
 node('files','records',4,'审计、信誉与考核','审计落盘 / 信誉留在内存',[(T,'finish_task'),('server/audit.py','save_round'),('server/evaluation.py','save_evaluation_report')],type='database'),
 node('tests','records',5,'按需运行安全自检','独立于正常计算流程',[(G,'_run_security_tests'),('server/security_tests.py','create_report')],type='security'),
 node('shortage','reject',2,'不足则拒绝启动','提示还缺多少在线节点',[(G,'_run_operation')],type='security',icon='failure'),
 ],[
 edge('power','idle'),edge('idle','listen'),edge('listen','manual','就绪后手动连接'),edge('manual','online','AUTH / 心跳'),
 edge('online','enough','登记在线'),edge('enough','restart','足够','security'),edge('enough','shortage','不足','security','error'),
 edge('restart','reconnect','旧连接断开'),edge('reconnect','dispatch','重新 AUTH'),edge('dispatch','compute','签名 TASK','security'),
 edge('compute','vote','加密 RESULT','security'),edge('vote','dispatch','非末轮','dashed','return'),edge('vote','complete','末轮'),
 edge('vote','files','成功表决'),edge('complete','stay'),edge('files','view','读取记录'),edge('view','tests','用户点击','dashed','branch'),
 edge('provision','listen','读取凭据与密钥','dashed')
 ],[
 ('cyan','如何读这张总览',['同一个子任务发给多个不同节点；节点在服务端线程池中并发执行。','空闲服务和带任务服务是两个先后启动的进程：点击运行会停止旧服务，再启动新服务；持续客户端负责重连。','数字签名保护 TASK；加密安全信封保护任务、结果和心跳。']),
 ('amber','按当前实现理解',['客户端网络层仍有三个仅声明的接口；这张图追踪现有调用与分支，不代表当前源码已完整链接验证。','这里从开机后的人工启动开始；没有新增操作系统开机自启。','后续四张图展开认证、计算、表决和异常分支。'])
 ])

diagram('02-auth-channel','认证与安全消息 · 双方怎样建立信任',[
 ('client','客户端身份准备与服务端核验',False),('server','服务端认证与会话建立',False),
 ('sender','安全消息发送端（C → S 或 S → C）',False),('receiver','安全消息接收端',False),('errors','认证与消息拒绝',True)], [
 node('load','client',0,'读取节点凭据','计算自身 EXE 的 SHA-256',[(C,'run_client'),('client/credentials.c','load_node_credential')],type='security'),
 node('auth','client',1,'构造并发送 AUTH','时间戳、随机数和 HMAC',[(C,'run_client')],type='messagebus'),
 node('verifyserver','client',4,'核验服务端证明','通过后派生同一会话密钥',[(C,'run_client')],type='security'),
 node('ready','client',5,'安全会话建立','双向序号从 1 开始',[(C,'run_client'),(SC,'__init__')],type='security',icon='success'),
 node('checkauth','server',2,'认证检查通过？','身份 / 许可 / 时间 / nonce',[(A,'authenticate')],type='security',icon='decision'),
 node('authok','server',3,'返回 AUTH_OK','会话 ID、随机数、服务端证明',[(A,'create_session'),(T,'handle_client')],type='security'),
 node('payload','sender',0,'业务 JSON','action 与具体业务字段',[(T,'_send_secure'),(C,'send_secure')]),
 node('seq','sender',1,'序号加一与新 nonce','区分 C2S 和 S2C',[(SC,'protect_server_message'),('client/secure_channel.c','protect_client_message')],type='security'),
 node('encrypt','sender',2,'加密并计算标签','HMAC 密钥流 / 再做 HMAC',[(SC,'encrypt_message')],type='security'),
 node('frame','sender',3,'发送 SECURE 帧','P13/1 Header + JSON Body',[(T,'_send_secure'),(C,'send_secure')],type='messagebus'),
 node('envelope','receiver',3,'校验安全信封','会话、方向、严格序号与标签',[(SC,'decrypt_message'),('client/secure_channel.c','open_server_message')],type='security',icon='decision'),
 node('decrypt','receiver',4,'校验通过后解密','解析业务 JSON 与 action',[(SC,'decrypt_message'),(C,'receive_secure_any')],type='security'),
 node('business','receiver',5,'交给对应业务','心跳 / TASK / RESULT / WAIT',[(T,'_receive_secure_any'),(C,'receive_secure_any')]),
 node('authfail','errors',2,'认证失败拒绝连接','记录事件，尽量返回 401',[(T,'handle_client')],type='security',icon='failure'),
 node('proofbad','errors',4,'服务端证明不符','客户端停止，本次返回 2',[(C,'run_client')],type='security',icon='failure'),
 node('msgbad','errors',3,'篡改或重放被拒绝','错误响应后结束本次连接',[(T,'handle_client'),(SC,'decrypt_message')],type='security',icon='failure'),
 ],[
 edge('load','auth'),edge('auth','checkauth','AUTH'),edge('checkauth','authok','通过','security'),edge('authok','verifyserver','AUTH_OK'),
 edge('verifyserver','ready','证明有效','security'),edge('checkauth','authfail','不通过','security','error'),edge('verifyserver','proofbad','无效','security','error'),
 edge('payload','seq'),edge('seq','encrypt'),edge('encrypt','frame'),edge('frame','envelope'),edge('envelope','decrypt','通过','security'),edge('decrypt','business'),
 edge('envelope','msgbad','失败','security','error')
 ],[
 ('cyan','认证字段与会话公式',['AUTH 包含 node_id、license_id、timestamp、client_nonce、exe_hash、auth_tag、persistent；不发送 auth_key。','服务端检查许可证归属与有效期、±60 秒时间窗、登录随机数去重、非空 EXE 白名单及 HMAC。','session_key = HMAC(auth_key, SESSION|client_nonce|server_nonce|session_id)。客户端还用 SERVER|... 核验服务端证明。']),
 ('amber','信封保护范围',['安全信封包含 session_id、sequence、nonce、ciphertext、tag；方向、会话、序号、nonce 和密文共同参与 HMAC。','不是 TLS / AES-GCM；外层 Header 的状态码与长度不在认证标签内。EXE 哈希是客户端上报值，不是硬件远程证明。','SESSION_TIMEOUT_SECONDS 虽有定义，但当前没有强制会话到期换钥流程；不要理解为每 30 秒自动换钥。'])
 ],['load','auth','checkauth','authok','verifyserver','ready'])

diagram('03-task-compute','任务签名、客户端计算与结果回传',[
 ('server','服务端任务调度与签名',False),('client','客户端执行与证明生成',False),
 ('modes','可选演示模式与阻断',True),('transport','传输层与后续处理',False)], [
 node('reserve','server',0,'尝试预留本轮任务','当前有效、未领取且名额未满',[(T,'_try_reserve_task')],icon='decision'),
 node('sign','server',1,'生成水印并 RSA 签名','任务 ID / 运算 / 起止区间',[(T,'handle_client'),('server/signature.py','sign_task'),('server/task_state.py','get_task_id')],type='security'),
 node('task','server',2,'加密下发 TASK','四种运算之一与签名',[(T,'handle_client')],type='messagebus'),
 node('verify','client',2,'检查字段并验签','公钥验证 RSA-2048 / SHA-256',[(C,'run_client'),('client/signature.c','verify_task_signature')],type='security',icon='decision'),
 node('calc','client',3,'区间拆四段计算','求和 / 计数 / 最小 / 最大',[('client/merkle.c','create_result_proof'),('client/operations.c','calculate_operation')]),
 node('merkle','client',4,'合并并生成 Merkle 根','四步值 → 四叶 → 两父 → 根',[('client/merkle.c','create_result_proof'),('client/merkle.c','build_merkle_root')],type='security'),
 node('result','client',5,'提交 RESULT','总值、四步值与根摘要',[(C,'run_client')],type='messagebus'),
 node('tamper','modes',1,'tamper 模式','验签前把任务终点加 1',[(C,'run_client')],type='security'),
 node('bad','modes',2,'验签失败不执行','返回码 2，图形端停止重连',[(C,'run_client'),(CG,'client_worker')],type='security',icon='failure'),
 node('wrong','modes',3,'wrong 模式','修改一步，再重建自洽证明',[('client/merkle.c','create_result_proof'),('client/operations.c','change_step_for_wrong_test')],type='security'),
 node('wait','transport',0,'无任务可领取','持续模式 WAIT；单次模式 409',[(T,'handle_client')],type='messagebus',icon='waiting'),
 node('proof','transport',5,'进入服务端结果验证','详见结果表决图',[(T,'_store_result')],type='security'),
 ],[
 edge('reserve','sign','可分配'),edge('reserve','wait','不可分配','dashed','branch'),edge('sign','task','签名 TASK','security'),edge('task','verify'),
 edge('verify','calc','验签通过','security'),edge('verify','bad','失败','security','error'),edge('calc','merkle','normal'),edge('calc','wrong','wrong','dashed','branch'),edge('wrong','merkle'),
 edge('task','tamper','演示分支','dashed','branch'),edge('tamper','verify','改后再验'),edge('merkle','result'),edge('result','proof','加密上传','security'),
 ],[
 ('cyan','签名与证明分别保护什么',['签名文本为 task_id|operation|start|end，使用服务端私钥签名；客户端从 task_public.key 读取公钥。','任务 ID 含随机会话水印和轮次，任务区间按总区间与子任务数平衡划分。','步骤值转换为十进制字符串后做 SHA-256；拼接的是十六进制摘要文本。RESULT 携带全部四个步骤，不是抽样 Merkle 路径。']),
 ('amber','当前实现边界',['实际领取函数检查任务状态、轮次、节点是否已领取和名额；没有使用低信誉或恶意节点名单阻止领取。','wrong 模式会提交自洽但错误的计算结果；Merkle 一致性可通过，最终正确性仍依赖多数表决。','四段是计算步骤；界面 25% / 50% / 75% / 100% 是流程阶段提示，不是逐段实时算量。'])
 ],['reserve','sign','task','verify','calc','merkle','result'])

diagram('04-results','结果验证、严格多数、信誉与审计',[
 ('receive','服务端接收与共享状态',False),('vote','表决、汇总与资格计算',False),
 ('files','业务审计与考核文件',False),('reply','轮次推进与客户端回执',False),('failure','结果拒绝与无多数分支',True)], [
 node('validate','receive',0,'验证 RESULT','身份、任务、四步值与根',[(T,'_store_result'),('server/merkle.py','verify_result_proof')],type='security',icon='decision'),
 node('store','receive',1,'加锁存入本轮结果','拒绝重复与已过期任务',[(T,'_store_result')]),
 node('count','receive',2,'本轮结果收齐？','数量等于 REQUIRED_NODES',[(T,'_store_result')],type='security',icon='decision'),
 node('majority','vote',2,'存在严格多数？','同一数值票数超过一半',[(T,'choose_majority'),(T,'finish_task')],type='security',icon='decision'),
 node('merge','vote',3,'采纳并合并子任务','累计 trusted_results',[(T,'finish_task'),('server/operations.py','merge_values')]),
 node('rep','vote',4,'更新信誉与资格','正确 +5 / 错误 −15',[(T,'update_reputation'),('server/scheduler.py','choose_important_task_nodes')],type='security'),
 node('audit','files',4,'保存本轮业务审计','data/audit.jsonl',[(T,'finish_task'),('server/audit.py','save_round')],type='database'),
 node('eval','files',5,'末轮生成考核报告','误差 / 安全开销 / 恶意比例',[('server/evaluation.py','create_evaluation_report'),('server/evaluation.py','save_evaluation_report')],type='database'),
 node('advance','reply',4,'结束或推进轮次','末轮 completed；否则 round+1',[(T,'_store_result'),('server/task_state.py','start_next_round')],icon='decision'),
 node('ack','reply',5,'返回 ACCEPTED','已接收，不保证赢得多数',[(T,'handle_client')],type='messagebus',icon='success'),
 node('reject','failure',0,'拒绝本次提交','403 / 409 / 422 等',[(T,'_store_result'),(T,'handle_client')],type='security',icon='failure'),
 node('nomajor','failure',2,'没有严格多数','finish_task 返回 False',[(T,'finish_task')],type='security',icon='failure'),
 node('nullaudit','failure',3,'保存失败审计','可信值为 null；不更新信誉',[(T,'finish_task'),('server/audit.py','save_round')],type='database'),
 ],[
 edge('validate','store','通过','security'),edge('validate','reject','失败','security','error'),edge('store','count'),edge('count','majority','收齐'),
 edge('count','ack','未收齐'),edge('majority','merge','有多数'),edge('merge','rep'),edge('rep','audit','本轮记录'),edge('audit','eval','仅末轮','dashed','branch'),
 edge('audit','advance'),edge('advance','ack'),edge('majority','nomajor','无多数','security','error'),edge('nomajor','nullaudit'),edge('nullaudit','advance','当前仍推进','dashed'),
 ],[
 ('cyan','信誉规则与最终输出',['初始信誉为 60，正确奖励 5，错误扣 15，限制在 0～100；累计第 5 次错误标记恶意，正确轮次不会清零错误计数。','重要任务资格要求信誉至少 60 且不在恶意集合；当前只是计算名单，没有接入领取拦截。','业务审计保存结果、证明、表决、合并值、信誉和异常节点；最后一轮成功表决时写 evaluation.json。']),
 ('amber','失败和回执的实际含义',['无多数只记失败审计；调用方没有检查 finish_task 的 False，仍可能推进下一轮或标记完成，没有自动重投机制。','ACCEPTED 只确认此节点结果被接收。RESULT_ACCEPTED 另外写安全日志；其他节点不必等本轮表决结束才收到回执。','考核安全开销来自 Python 固定微基准，不是整个 C/S 流程的端到端性能。信誉、轮次与结果集合保存在内存，重启会重建。'])
 ],['validate','store','count','majority','merge','rep','audit','advance','ack'])

diagram('05-lifecycle','心跳等待、异常重连、退出与独立自检',[
 ('server','服务端连接处理',False),('client','持续在线客户端',False),
 ('recover','异常与重连分支',True),('cleanup','资源清理与离线',False),('checks','按需运行的检查与记录',False)], [
 node('unavailable','server',0,'暂无可领取任务','未启用 / 已领 / 名额满 / 完成',[(T,'_try_reserve_task')],icon='decision'),
 node('wait','server',1,'发送 WAIT','retry_after=2 / all_complete',[(T,'handle_client')],type='messagebus'),
 node('heartbeat','server',3,'核验并确认心跳','sent_at>0 / 更新在线状态',[(T,'handle_client')],type='messagebus'),
 node('retrytask','server',4,'再次尝试领取','有任务则进入签名计算流程',[(T,'handle_client')],icon='decision'),
 node('sleep','client',1,'收到 WAIT 后等待','默认 2 秒；只接受 1～5 秒',[(C,'run_client')],icon='clock'),
 node('sendhb','client',2,'发送 HEARTBEAT','加密后等待 HEARTBEAT_ACK',[(C,'send_heartbeat'),(C,'run_client')],type='messagebus'),
 node('manualstop','client',4,'用户主动断开','设置停止标志；尝试 LOGOUT',[(C,'request_client_stop'),(C,'run_client')],type='external',icon='stop'),
 node('single','recover',0,'单次模式无任务','409 后结束本次连接',[(T,'handle_client')],type='security'),
 node('error','recover',1,'协议失败、超时或断线','服务端尽量回 ERROR 并记日志',[(T,'handle_client')],type='security',icon='failure'),
 node('exitcode','recover',2,'图形端检查退出原因','主动停止 / 返回码 2 不重连',[(CG,'client_worker')],type='security',icon='decision'),
 node('again','recover',3,'其他中断等待 2 秒','重新进入完整认证流程',[(CG,'client_worker')],type='messagebus'),
 node('authagain','recover',4,'再次连接与认证','新随机数、新会话、新序号',[(C,'run_client')],type='security'),
 node('free','cleanup',1,'服务端释放未提交名额','标记离线 / 外层关闭连接',[(T,'handle_client'),(S,'serve')]),
 node('zero','cleanup',2,'客户端关闭与清零','清理凭据、会话密钥和临时值',[(C,'run_client'),('client/security.c','clear_sensitive')],type='security'),
 node('logout','cleanup',4,'等待分支处理 LOGOUT','记录退出；结束连接',[(T,'handle_client')],type='messagebus'),
 node('end','cleanup',5,'本次连接结束','单次成功 / 人工退出 / 认证阻断',[(C,'run_client'),(CG,'client_worker')],icon='stop'),
 node('test','checks',0,'用户点击安全自检','或独立运行 security_tests.py',[(G,'_run_security_tests'),('server/security_tests.py','create_report')],type='external'),
 node('cases','checks',1,'执行 10 项基础检查','篡改 / 重放 / 身份 / 长度等',[('server/security_tests.py','create_report')],type='security'),
 node('testfile','checks',2,'保存并显示自检结果','data/security_tests.json',[('server/security_tests.py','create_report'),(G,'_refresh_security')],type='database'),
 node('events','checks',3,'安全事件持续落盘','data/security_audit.jsonl',[('server/security_audit.py','record_security_event'),(T,'handle_client')],type='database'),
 node('stopserver','checks',5,'停止服务或关闭中心','终止服务进程，客户端按规则重连',[(P,'stop_server'),(G,'_close_window')],type='external',icon='stop'),
 ],[
 edge('unavailable','wait','持续模式'),edge('unavailable','single','单次模式','dashed','branch'),edge('wait','sleep'),edge('sleep','sendhb'),edge('sendhb','heartbeat','加密心跳','security'),
 edge('heartbeat','retrytask','ACK'),edge('retrytask','unavailable','仍无任务','dashed','return'),edge('sleep','manualstop','用户断开','dashed','branch'),edge('manualstop','logout'),edge('logout','end'),
 edge('error','free'),edge('single','free'),edge('free','zero'),edge('zero','exitcode'),edge('exitcode','again','允许重连'),edge('again','authagain'),edge('exitcode','end','人工停止或码 2'),
 edge('test','cases'),edge('cases','testfile'),edge('error','events','记录事件','dashed'),edge('stopserver','error','旧连接中断','dashed'),
 ],[
 ('cyan','连接循环与退出',['首次认证后先做一次 HEARTBEAT / ACK；之后持续客户端在 WAIT、心跳、任务和结果提交之间循环。','完成全部任务后持续客户端仍会等待并心跳；没有自动关闭所有客户端。单次客户端成功提交后清理退出。','GUI 外层循环遇一般中断会每 2 秒重试；身份或任务验签失败返回 2 时不再重连。'],),
 ('amber','异常处理的真实边界',['LOGOUT 当前只在服务端等待分支处理，计算或等结果阶段没有独立取消协议；正在阻塞的操作不会被停止标志立即打断。','服务端套接字超时为 8 秒；客户端底层收发配置 5 秒。network_connect_retry、network_send_bytes、network_receive_exact 当前只有声明，完整联调仍需补齐。','10 项自检不是完整渗透测试，也不能证明当前 C 客户端能重新构建运行；TEE 未实现。'])
 ])

print('Authored five complete workflow candidates.')
