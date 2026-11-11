import json
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT=Path('F:/project13'); OUT=ROOT/'deliverables'
V=json.loads((ROOT/'work/documents/verification.json').read_text(encoding='utf-8'))
PROJECT='分布式计算任务安全分发与结果审计平台'

def font(run,size=None,bold=None):
    run.font.name='宋体'
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
    if size:run.font.size=Pt(size)
    if bold is not None:run.bold=bold
    run.font.color.rgb=RGBColor(0,0,0)

class Paper:
    def __init__(self,title,code):
        self.title=title;self.doc=Document();self.md=[]
        s=self.doc.sections[0]
        s.page_width=Cm(21);s.page_height=Cm(29.7)
        s.top_margin=Cm(2.1);s.bottom_margin=Cm(2.0)
        s.left_margin=Cm(2.3);s.right_margin=Cm(2.3)
        normal=self.doc.styles['Normal'];normal.font.name='宋体';normal.font.size=Pt(10.5)
        normal.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
        normal.paragraph_format.line_spacing=1.25
        normal.paragraph_format.space_after=Pt(6)
        for name,size in [('Title',23),('Heading 1',15),('Heading 2',12)]:
            st=self.doc.styles[name];st.font.name='黑体';st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
            st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'黑体')
            st.paragraph_format.space_before=Pt(10);st.paragraph_format.space_after=Pt(7)
        p=self.doc.add_paragraph(title,'Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        p=self.doc.add_paragraph(PROJECT);p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:font(r,12,True)
        p=self.doc.add_paragraph(f'项目13  |  文档编号 {code}  |  版本 1.0  |  日期 2026年11月11日')
        p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:font(r,9)
        self.p('班级：________________    姓名：________________    学号：________________')
        self.md.extend([f'# {title}',PROJECT,f'文档编号：{code}；版本：1.0；日期：2026年11月11日。'])
        foot=s.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
        r=foot.add_run('第 ');font(r,9)
        f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');foot._p.append(f)
        r=foot.add_run(' 页');font(r,9)
    def p(self,text):
        self.doc.add_paragraph(text);self.md.append(text)
    def h(self,text,level=1):
        self.doc.add_heading(text,level);self.md.append('#'*(level+1)+' '+text)
    def page(self):self.doc.add_page_break()
    def table(self,headers,rows,widths=None):
        t=self.doc.add_table(rows=1, cols=len(headers));t.style='Table Grid';t.autofit=False
        if widths:
            for c,w in zip(t.columns,widths):c.width=Cm(w)
        for c,txt in zip(t.rows[0].cells,headers):c.text=str(txt)
        for row in rows:
            for c,txt in zip(t.add_row().cells,row):c.text=str(txt)
        for i,row in enumerate(t.rows):
            trpr=row._tr.get_or_add_trPr();trpr.append(OxmlElement('w:cantSplit'))
            if i==0:
                trpr.append(OxmlElement('w:tblHeader'))
            for j,c in enumerate(row.cells):
                if widths:c.width=Cm(widths[j])
                if i==0:
                    shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'EEEEEE');c._tc.get_or_add_tcPr().append(shade)
                for p in c.paragraphs:
                    p.paragraph_format.space_after=Pt(3);p.paragraph_format.space_before=Pt(3);p.paragraph_format.line_spacing=1.1
                    for r in p.runs:font(r,9,i==0)
        self.md.extend(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|'])
        self.md.extend('| '+' | '.join(str(x).replace('\n','；') for x in row)+' |' for row in rows)
    def code(self,text):
        for line in text.splitlines():
            p=self.doc.add_paragraph();p.paragraph_format.space_after=Pt(1);p.paragraph_format.line_spacing=1.05
            r=p.add_run(line);font(r,8.5);r.font.name='Consolas'
        self.md.append('```text\n'+text+'\n```')
    def save(self):
        for element in [self.doc.styles.element, self.doc.element]:
            for b in list(element.iter(qn('w:pBdr'))):b.getparent().remove(b)
            for f in element.iter(qn('w:rFonts')):
                for a in ['asciiTheme','hAnsiTheme','eastAsiaTheme','cstheme','csTheme']:
                    f.attrib.pop(qn('w:'+a),None)
        self.doc.core_properties.title=self.title
        self.doc.core_properties.subject=PROJECT
        self.doc.core_properties.author=''
        self.doc.save(OUT/(self.title+'.docx'))
        (ROOT/'work/documents'/ (self.title+'.md')).write_text('\n\n'.join(self.md),encoding='utf-8')

d=Paper('系统设计说明书','P13-SD-001')
d.h('1 系统概述')
d.p('本系统面向课程实验中的分布式计算场景，由 Python 服务端与 Windows C 客户端组成。服务端把整数区间拆分为子任务，分配给多个独立节点，收集带完整性证明的结果，通过严格多数表决形成可信结果，并保存任务、信誉和安全事件记录。系统提供求和、计数、最小值和最大值四类运算。')
d.p('设计目标是把任务分发、节点认证、结果一致性校验和审计串联为可演示的完整流程。系统信任服务端和部署阶段发放的密钥；结果可靠性依赖参与表决节点中存在诚实多数。Merkle 证明校验步骤值与总结果的一致性，不能单独证明节点执行过程真实或计算正确。')
d.h('1.1 功能范围',2)
d.table(['功能','设计与处理方式'],[
('任务管理','设置运算、总区间、子任务数和冗余节点数；逐轮推进子任务。'),
('节点接入','校验许可证、时间戳、随机数、程序哈希和HMAC身份标签。'),
('安全分发','建立临时会话密钥，对业务消息加密并认证；任务附RSA签名。'),
('计算验证','客户端四段计算，提交步骤值与Merkle根；服务端验证并投票。'),
('信誉与审计','按结果更新分值、识别累计错误节点，记录业务和安全事件。'),
('可视化','服务端控制中心展示运行、节点、日志、审计、考核和自检信息。')],[2.5,13.9])
d.h('1.2 部署与默认配置',2)
d.p('默认监听地址为 127.0.0.1:8888，属于同机多进程演示。默认计算区间为 1 至 1000，拆分为 5 个子任务，每轮配置 10 个节点，线程池上限为 64。每轮至少 3 个节点，每个子任务至少包含 4 个整数。跨机器运行需同时调整客户端与服务端地址及部署配置，本版本默认配置不直接实现远程接入。')
d.page()
d.h('2 总体架构与模块职责')
d.p('系统按界面与控制、业务、安全、网络和持久化分工。客户端通过 TCP 连接服务端，认证后以 SECURE 帧承载业务动作。服务端以 select 等待监听套接字就绪，把已接受连接提交给线程池；每个工作线程处理一个节点会话，共享任务状态由可重入锁保护。')
d.code('服务端控制中心  →  参数校验与进程控制\n                           ↓\n节点客户端  ← TCP P13/1 →  服务端认证与会话处理\n 四段计算                  任务拆分 → 冗余分发\n RSA验签                   证明校验 → 多数表决\n Merkle构造                结果合并 → 信誉更新\n                           ↓\n                   业务审计 / 安全审计 / 考核文件')
d.table(['模块','主要文件','职责'],[
('网络与协议','server.py / protocol.py','监听、并发接入、分帧、状态码和JSON编解码。'),
('认证与会话','credential_store.py / secure_channel.py','许可证、程序哈希和HMAC认证，会话密钥及抗重放。'),
('任务业务','task_service.py / task_state.py','领取任务、提交验证、轮次推进、共享状态加锁。'),
('计算与验证','task_planner.py / operations.py / merkle.py','区间划分、运算及合并、四步骤证明校验。'),
('签名与密钥','signature.py / rsa_keys.py','RSA-2048私钥生成、SHA-256任务签名。'),
('信誉与记录','scheduler.py / audit.py / security_audit.py','资格筛选、业务与安全事件分开记录。'),
('界面与评估','gui.py / process_manager.py / evaluation.py','启动控制、状态展示和指标计算。'),
('客户端','client_logic.c及network、protocol、security等模块','认证、验签、计算、结果提交与在线等待。')],[2.3,6.5,7.6])
d.h('2.1 并发与一致性',2)
d.p('任务领取时在锁内检查轮次、已分配节点集合和名额；提交时在锁内校验当前任务与重复结果。结果按节点 ID 保存，每轮同一节点最多计入一次。达到配置节点数才进行表决。未成功提交即断开时释放已分配名额，供其他节点领取。')
d.page()
d.h('3 任务计算与结果可信机制')
d.h('3.1 区间拆分与运算',2)
d.p('设总区间为 [A,B]，元素数 N=B−A+1，子任务数为 K，轮次 r 从 1 开始。子区间起点为 A+⌊N(r−1)/K⌋，终点为 A+⌊Nr/K⌋−1。该划分覆盖整个区间且互不重叠；不能整除时长度最多相差一个元素。客户端再以相同原则把领取区间拆为四段。')
d.table(['运算标识','子任务计算','总结果合并'],[
('SUM_RANGE','区间内各整数求和','对子任务结果求和'),('COUNT_RANGE','区间内整数个数','对子任务计数求和'),('MIN_RANGE','区间最小整数','取子任务最小值的最小值'),('MAX_RANGE','区间最大整数','取子任务最大值的最大值')],[4.5,6.1,5.8])
d.h('3.2 任务水印与完整性',2)
d.p('任务 ID 形如 task-会话片段-三位轮次号。服务端把 task_id、operation、start、end 以竖线连接，使用 RSA-2048 与 SHA-256/PKCS#1 v1.5 签名。客户端用部署公钥验签后执行。任务 ID 的随机片段用于区分运行批次，不等同于硬件可信执行证明。')
d.p('每个步骤结果的十进制文本经过 SHA-256 得到叶子哈希，相邻叶子的十六进制哈希文本拼接后再次哈希，最终得到根。提交包含四个步骤值、根和合并值。服务端重新合并步骤并重建根；若只修改总值或根，证明不匹配。攻击者若同时构造自洽错误步骤和根，仍需依靠冗余表决识别。')
d.h('3.3 表决与信誉',2)
d.p('严格多数门槛为 ⌊已收集结果数/2⌋+1，当前流程收齐每轮配置数量后投票。存在严格多数时选其值并累计整合结果。无严格多数时保存失败审计，finish_task 返回失败；当前调用方仍可能推进轮次，因此不能把轮次结束等同于任务成功。')
d.p('节点初始信誉为 60，正确一次加 5，错误一次减 15，限制在 0 至 100。错误次数累计达到 5 次时加入恶意节点集合；正确轮次不清空既有错误计数。信誉至少 60 且未被识别为恶意的节点进入重要任务资格名单。当前普通领取路径未引用该名单，资格筛选与实际强制拒发之间仍需补齐。')
d.page()
d.h('4 安全与数据设计')
d.h('4.1 认证和安全会话',2)
d.p('部署阶段生成独立节点身份密钥、许可证和程序 SHA-256 白名单。登录请求携带节点 ID、许可证 ID、Unix 秒时间戳、16字节客户端随机数、程序哈希及 HMAC-SHA256 标签；persistent 标志也纳入认证文本。服务端验证许可证归属、有效期、正负60秒时间窗、随机数重复、白名单及身份标签。')
d.p('认证成功后，服务端返回会话 ID、服务端随机数和身份确认标签。双方以身份密钥对 SESSION 前缀、双方随机数和会话 ID 进行 HMAC 派生。业务消息使用 HMAC 派生密钥流与明文异或，外加覆盖方向、会话、序号、nonce和密文的认证标签。双向序号各自从1开始严格递增。该方案属于本项目自定义安全通道，不应当表述为 TLS 或标准 AES 加密。')
d.h('4.2 数据对象',2)
d.table(['对象','关键字段','存储方式'],[
('任务状态','会话片段、轮次、已分配节点、结果、证明、可信值','内存；RLock保护'),
('节点信誉','reputation_scores、wrong_rounds、malicious_nodes','内存；审计留存快照'),
('业务审计','任务ID、轮次、范围、节点结果、证明、信誉、考核','data/audit.jsonl逐行追加'),
('安全事件','事件类型、节点、地址、详情与时间','data/security_audit.jsonl'),
('考核及自检','误差、安全开销、恶意比例；自检用例结果','evaluation.json / security_tests.json'),
('密钥与凭据','服务端私钥、节点身份密钥、许可证、公钥','受控部署文件；不放入报告正文')],[2.5,8.0,5.9])
d.h('4.3 异常与限制',2)
d.p('错误类型包括认证失败、身份不匹配、超长帧、证明无效、重复提交、网络超时及内部错误。认证前返回 ERROR，建立会话后返回携带 ERROR 动作的 SECURE 帧。服务端会话处理的套接字超时实际为 8 秒；配置中的 30 秒会话超时尚未形成独立强制过期流程。')
d.p('任务与信誉状态未使用数据库，服务端重启后内存状态重置。服务端等待全部配置结果，尚缺少业务级任务截止时间和自动补位策略。TEE远程证明未实现。C客户端使用 long 存储数值，在 Windows 上通常为32位，输入及中间结果需控制在可表示范围内。')
d.page()
d.h('5 部署使用与当前交付状态')
d.h('5.1 环境和操作流程',2)
d.p('运行环境为 Windows、Python 3、支持C11和Windows系统库的C编译器。历史环境记录列出了 Python 3.14.6 与 GCC 4.9.2。本次文档复核使用配套 Python 3.12.14，仅验证明确列出的模块与算法，不代替历史机器的客户端构建验证。')
d.p('操作顺序：先完成客户端构建及凭据签发，启动服务端控制中心并进入等待状态；手动打开使用不同节点 ID 的客户端，认证并保持在线；确认可用节点数量后选择运算、输入参数并开始任务；观察分段进度、表决结果及审计；任务完成后客户端可继续心跳等待，用户主动断开时发送 LOGOUT。')
d.code('工程根目录下的主要入口\nPython服务端控制中心：python server/gui.py\n凭据与白名单刷新：    python server/provision.py\n安全自检：            python server/security_tests.py\n控制台客户端：        client/client.exe node-01 normal stay')
d.p('重新编译客户端后应重新执行凭据签发脚本更新程序哈希白名单。首次签发和安全自检会写入项目数据文件，需在准备正式答辩演示时执行；本次复核没有覆盖原有凭据和历史审计。')
d.h('5.2 需要完成的工程项',2)
d.table(['项目','本次核对结果','完成条件'],[
('客户端网络接口','network.h声明的connect_retry、send_bytes、receive_exact在当前network.c中缺少实现','补齐定义并重新构建两个客户端，再进行TCP分段联调'),
('启动任务配置','README提到的.vscode/tasks.json在当前目录未找到','补齐任务文件或改用已核验的手动启动流程'),
('重要任务约束','可生成资格名单，但普通任务领取未强制使用','在任务分配入口落实资格判定并添加验证'),
('表决失败处理','无多数后调用链仍可推进轮次','以表决成功为推进条件或增加失败重试状态')],[2.7,8.1,5.6])
d.h('5.3 设计依据',2)
d.p('主要依据：README.md、PROTOCOL.md、ENVIRONMENT.md；server 下的 config、server、task_service、task_state、task_planner、operations、credential_store、secure_channel、signature、merkle、scheduler、audit、evaluation；client 下的 client_logic、network、protocol、merkle。本文描述实现机制和明确的现存缺口，实际测试结论见配套测试验证报告。')
d.save()

d=Paper('通信协议文档','P13-CP-001')
d.h('1 适用范围与报文格式')
d.p('P13/1 是本项目客户端与服务端之间的 TCP 应用层协议，覆盖身份认证、在线心跳、任务分发、结果提交和退出。默认连接 127.0.0.1:8888。认证前使用 AUTH、AUTH_OK 和 ERROR 帧；认证后统一使用 SECURE 帧，具体业务类型放在解密后的 action 字段中。')
d.code('P13/1 <message_type> <status> <body_length>\n\n<JSON Body>')
d.p('上式第一行末尾只有一个 LF 字节，即 0x0A；图示中的空行仅用于区分 Header 与 Body，不发送额外空行。Header使用ASCII，Body使用UTF-8。body_length是Body编码后的字节数，不是字符数，也不包含Header。Body不以换行作为边界。')
d.table(['字段','定义'],[
('版本','固定字符串 P13/1'),('message_type','AUTH、AUTH_OK、SECURE或ERROR；Python端允许字母数字及下划线'),('status','客户端请求通常为0；服务端成功为200，失败使用对应状态码'),('body_length','JSON对象编码后的字节数；至少2字节'),('JSON规则','顶层必须为对象；联调使用紧凑JSON，不在键与冒号之间加入空白')],[3.4,13.0])
d.h('1.1 边界与兼容约束',2)
d.p('Python端配置Header上限为128字节、Body上限为8192字节。C端Header数组为128字节，Body数组为8192字节，并为字符串终止符预留空间；跨端报文应使用保守公共范围：Header含LF不超过127字节，Body不超过8191字节。密文采用十六进制编码后约膨胀两倍，因此业务明文的可用长度明显小于外层Body上限。')
d.p('Python端按单字节读取到LF，再循环读取指定长度Body。C协议模块按行读取Header并调用network_receive_exact读取Body；当前网络实现缺少该接口定义，且现有network_receive_line可能丢弃同次recv中LF后的数据。客户端粘包拆包能力必须补齐网络实现后再做联调确认。')
d.h('1.2 最小帧示例',2)
d.code('P13/1 ERROR 400 16\n{"detail":"bad"}')
d.p('此示例Body恰为16个ASCII字节。实现应根据实际UTF-8编码动态计算长度，不能照搬带示意字段报文的固定长度。')
d.page()
d.h('2 身份认证与密钥建立')
d.h('2.1 AUTH 请求',2)
d.p('方向为客户端至服务端，外层类型AUTH，状态0。所有字段使用下表名称；persistent推荐显式发送0或1。节点ID在C端限制为非空且少于64字节，只允许字母数字、短横线和下划线。')
d.table(['字段','类型与长度','含义'],[
('node_id','字符串','已签发凭据的节点标识，如node-01'),('license_id','字符串','与节点绑定的许可证ID'),('timestamp','整数','Unix秒时间戳；服务端允许±60秒'),('client_nonce','32位十六进制字符串','16字节安全随机数，登录去重'),('exe_hash','64位十六进制字符串','客户端可执行文件的SHA-256'),('auth_tag','64位十六进制字符串','使用节点身份密钥生成的HMAC-SHA256'),('persistent','整数0或1','0为单次任务，1为持续在线等待；未提供时服务端按false处理')],[3.3,5.3,7.8])
d.p('认证文本按以下顺序连接，不插入空格，timestamp与persistent使用十进制文本。auth_key为部署分发的32字节节点密钥，仅保存在凭据文件中，不随AUTH传输。')
d.code('auth_text = node_id|license_id|timestamp|client_nonce|exe_hash|persistent\nauth_tag  = HMAC-SHA256(auth_key, UTF8(auth_text)).hex()')
d.h('2.2 AUTH_OK 响应',2)
d.table(['字段','类型','说明'],[
('session_id','24位十六进制字符串','12字节随机会话标识'),('server_nonce','32位十六进制字符串','16字节服务端随机数'),('server_proof','64位十六进制字符串','服务端持有节点密钥的证明'),('license_status','字符串','成功时为valid'),('integrity_status','字符串','成功时为valid')],[3.7,5.0,7.7])
d.code('proof_text = SERVER|session_id|client_nonce|server_nonce\nserver_proof = HMAC-SHA256(auth_key, UTF8(proof_text)).hex()\nkey_text = SESSION|client_nonce|server_nonce|session_id\nsession_key = HMAC-SHA256(auth_key, UTF8(key_text))')
d.p('客户端先验证server_proof，再使用派生的32字节session_key进入安全会话。任何许可证归属、有效期、时间窗、随机数、程序白名单或身份标签不符合要求的请求均拒绝。当前实现中白名单非空时才执行哈希成员校验，部署验收应确认白名单已经生成。')
d.page()
d.h('3 安全信封与字节级计算')
d.p('认证后的外层报文类型固定为SECURE，Body为安全信封。请求外层状态为0，响应外层状态为200或错误状态。业务JSON加密前必须包含action字段。C2S表示客户端发送，S2C表示服务端发送，双方分别维护发送序号与接收序号，初始值为0，首条消息使用1。')
d.table(['字段','类型与格式','作用'],[
('session_id','字符串','必须与本连接建立的会话一致'),('sequence','正整数','必须等于该方向上预期的下一个序号'),('nonce','32位十六进制字符串','每条消息新生成16字节随机数'),('ciphertext','十六进制字符串','业务JSON的UTF-8字节加密结果'),('tag','64位十六进制字符串','覆盖方向、会话、序号、nonce和密文的认证标签')],[3.3,5.3,7.8])
d.h('3.1 加密算法',2)
d.p('先将业务对象序列化为紧凑JSON并编码为UTF-8。使用下式生成足够长度的密钥流，按长度截断，与明文字节逐位异或。密钥流计数器从0开始；sequence为8字节无符号大端序，counter为4字节无符号大端序，nonce使用原始16字节。方向和会话ID使用ASCII。')
d.code('prefix = ASCII(direction) || 0x7C || ASCII(session_id) || 0x7C\n         || BE64(sequence) || nonce\nblock[i] = HMAC-SHA256(session_key, prefix || BE32(i))\nstream = block[0] || block[1] || ...\nciphertext = plaintext XOR stream[0:len(plaintext)]')
d.h('3.2 认证标签与接收',2)
d.code('tag_text = direction|session_id|sequence|nonce_hex|ciphertext_hex\ntag = HMAC-SHA256(session_key, UTF8(tag_text)).hex()')
d.p('上述tag_text中的sequence为十进制文本，nonce和密文使用小写十六进制。接收端校验会话、严格序号、nonce长度和HMAC标签后，再解密并解析JSON对象。篡改、旧序号和方向不匹配应拒绝。Python SecureSession在验证失败时回退本次预增的接收序号。')
d.h('3.3 安全边界',2)
d.p('该信封认证文本未包含外层Header中的message_type、status或body_length；业务action在密文内部。当前方案没有临时密钥交换，不具备已证明的前向保密属性。源码定义的SESSION_TIMEOUT_SECONDS=30尚未形成可观察的强制会话到期检查；不得把它理解为30秒自动换钥。')
d.page()
d.h('4 业务动作与字段')
d.p('下表描述SECURE解密后的业务对象。除表中字段外，每个对象均须带action字符串。ACCEPTED表示结果已通过提交层检查并存入，不表示当前值最终赢得多数表决。')
d.table(['动作与方向','字段','处理规则'],[
('HEARTBEAT\nC → S','sent_at：整数','Unix秒时间戳；服务端当前只检查其大于0'),
('HEARTBEAT_ACK\nS → C','server_time：整数','服务端Unix秒时间'),
('WAIT\nS → C','retry_after：整数；all_complete：布尔','当前默认间隔2秒；C端接受1至5秒，否则回退2秒'),
('TASK\nS → C','task_id：字符串；operation：字符串；start、end：整数；signature：十六进制字符串','operation为四类运算标识之一；客户端必须先验签'),
('RESULT\nC → S','task_id、node_id：字符串；value：整数；merkle_root：字符串；proof_steps：字符串','任务与节点必须对应当前连接；证明一致且未重复提交'),
('ACCEPTED\nS → C','task_id：字符串','本节点结果已入库到本轮内存结果集合'),
('LOGOUT\nC → S','无额外字段','当前持续在线等待分支处理退出；不定义单独退出确认动作'),
('ERROR\nS → C','detail：字符串','外层status提供错误类别；客户端结束当前会话')],[3.4,7.4,5.6])
d.h('4.1 任务签名',2)
d.code('task_text = task_id|operation|start|end\nsignature = RSA-2048-SHA256-PKCS1-v1_5(task_text).hex()')
d.p('start和end使用有符号十进制文本，operation保持字母大小写。2048位RSA签名为256字节，十六进制表示为512字符。客户端使用client/task_public.key中的公钥验证；签名不匹配时停止执行。')
d.h('4.2 结果证明',2)
d.p('proof_steps不是数组，而是四个十进制整数以逗号连接的字符串，例如1275,3775,6275,8775。对每个值的十进制文本做SHA-256得到64字符小写十六进制叶子；相邻叶子文本拼接后再做SHA-256，最后拼接两个中间哈希文本并哈希得到根。拼接的是哈希文本，不是32字节原始摘要。')
d.p('示例：SUM_RANGE计算1至200，四步值为1275、3775、6275、8775，value为20100，merkle_root为11a35f8bb4b015ed2eea741b278b0f3fcaadbb17b2518033598ec9f3acd785f4。其他运算按对应合并规则得到value。')
d.page()
d.h('5 会话顺序与错误处理')
d.code('客户端                         服务端\nAUTH ------------------------> 许可证与身份认证\n     <---------------- AUTH_OK 会话参数与服务端证明\nSECURE / HEARTBEAT -----------> 验证序号和心跳\n     <--------- HEARTBEAT_ACK\n     <------------------ TASK  签名任务\n验签并四段计算\nSECURE / RESULT -------------> 身份、任务、证明、重复检查\n     <-------------- ACCEPTED\n     <------------------ WAIT 持续在线模式无新任务\nHEARTBEAT / ACK 循环，后续出现新TASK时继续执行\nSECURE / LOGOUT -------------> 等待分支退出并关闭连接')
d.p('持续在线客户端在完成一个任务后仍可等待下轮任务。非持续模式若当前轮次无法领取任务，服务端返回409并关闭连接。节点在已分配但未成功提交时断开，服务端释放该节点的领取名额。')
d.table(['状态码','含义','典型触发条件'],[
('200','成功','认证、心跳和提交处理成功'),('400','格式或顺序错误','Header、JSON、消息类型或action不符合要求'),('401','认证失败','凭据失败、安全信封校验失败'),('403','身份不匹配','RESULT中的节点或任务与分配不符'),('409','状态冲突','重复提交、任务过期、当前轮次无可领取任务'),('413','消息超限','长度非法或Body过大'),('422','结果不可处理','结果字段无效、Merkle证明不匹配；当前超时处理亦可能使用该码'),('500','服务端错误','未预期的内部异常')],[2.0,4.0,10.4])
d.p('认证前错误使用明文ERROR帧，Body为含detail的JSON对象；认证后尽量使用SECURE包裹ERROR动作。底层网络断开不保证能发送错误报文。服务端处理套接字超时为8秒，C网络文件对收发设置5秒超时，connect本身未实现独立超时控制。')
d.h('5.1 联调验收要点',2)
d.p('应验证跨端紧凑JSON、UTF-8字节长度、双向独立序号、连续帧与逐段发送、错误状态码、非空程序白名单、篡改和重放拒绝，以及持续在线时的WAIT循环。客户端缺失网络接口补齐前，当前Python端测试结果不能作为C端收包能力的验收依据。')
d.p('实现依据：server/protocol.py、credential_store.py、secure_channel.py、task_service.py、signature.py、merkle.py；client/protocol.c、client_logic.c、secure_channel.c、merkle.c与network.c。现有PROTOCOL.md作为概要参考，本文补充具体字段、字节级计算和兼容边界。')
d.save()

d=Paper('测试验证报告','P13-TV-001')
d.h('1 验证结论与范围')
d.p('本次于2026年11月11日完成源码核对、历史证据复核及17项模块级检查，17项均通过。历史记录支持区间计算、冗余表决和部分安全机制的演示结果；当前源码存在客户端网络接口缺失、重要任务资格未强制应用、无多数结果仍可能推进轮次等问题，现阶段不宜认定为完整系统验收通过。')
d.p('本次没有重新编译或启动C客户端，没有执行多节点GUI端到端演示，也没有重测整机性能。现有可执行文件与当前源码是否一致尚未核验。以下分别标注历史运行记录、本次模块复核和待完成事项，避免不同版本与测试层级混用。')
d.h('1.1 测试环境与证据',2)
d.table(['项','记录'],[
('当前工程','F:/project13，Windows环境'),('本次复核运行时','配套Python 3.12.14；服务端模块直接调用与语法解析'),('历史环境记录','ENVIRONMENT.md记载2026-10-04使用Python 3.14.6和GCC 4.9.2'),('历史业务证据','data/audit.jsonl，共'+str(sum(x['records'] for x in V['history']))+'条记录，'+str(len(V['history']))+'个任务批次'),('历史安全自检','data/security_tests.json，生成时间2026-10-05T11:42:27，10/10通过'),('当前考核快照','data/evaluation.json；内容与2026-10-14最后一批审计中的考核一致')],[3.5,12.9])
d.h('1.2 方法与判定',2)
d.p('功能检查以数学标准答案、严格多数门槛、四步证明一致性和配置边界为依据；安全检查以预期异常是否被拒绝为依据。性能阈值按项目代码取安全开销不超过30%，准确性按误差小于1%。恶意节点考核代码要求检测数大于0且检测比例不超过10%；该字段不是检测召回率，未注入恶意节点时也会为false。')
d.p('本次复用安全用例时关闭自动凭据签发和密钥生成，仅读取现有材料；没有调用会覆写历史自检报告的create_report。语法检查采用AST解析，不生成项目字节码缓存；既有审计、凭据和考核文件保持原内容。')
d.page()
d.h('2 历史任务运行结果')
d.h('2.1 五轮十节点求和记录',2)
d.p('选取2026年10月4日21时35分的task-1caf2a94批次。总区间1至1000，5轮，每轮10个结果。各轮有9个正常节点和1个错误结果节点，审计记录的可信子结果与数学标准答案一致。')
d.table(['轮次','区间','可信子结果','累计结果'],[(1,'1至200',20100,20100),(2,'201至400',60100,80200),(3,'401至600',100100,180300),(4,'601至800',140100,320400),(5,'801至1000',180100,500500)],[1.8,4.4,5.1,5.1])
d.p('最终误差为0.00%；第5轮审计列出node-10为恶意节点，恶意节点比例10.00%，malicious_detection_passed=true。该批次记录的安全开销为11.29%。这些结论属于既有批次，不是本次重新运行的端到端结果。')
d.h('2.2 不同批次和未通过记录',2)
d.table(['批次及时间','关键数据','评价'],[
('task-bf9442fc\n2026-10-04 21:27','3节点、单轮；结果210；开销331.45%','准确性通过；安全开销未通过'),
('task-66654387\n2026-10-05 11:32','5节点；识别1个恶意节点，占20%；开销9.94%','准确性通过；恶意比例考核未通过'),
('task-8d390faa\n2026-10-14 17:09','10节点、5轮；结果1252526275；开销9.32%；恶意集合为空','准确性和开销通过；恶意识别字段为false')],[5.0,7.0,4.4])
d.p('最新批次没有识别到恶意节点，不能由false推断检测算法必然失效，也不能据此声称恶意节点识别已经通过。需要明确注入比例、节点身份与轮次后重新测试。单轮3节点批次的高开销也必须保留，不能用其他批次的低开销替换。')
d.page()
d.h('3 本次模块检查结果')
d.p('以下17项于2026年11月11日执行。前10项复用安全测试函数，后7项补充语法、算法和协议边界。它们不启动业务监听端口，也不依赖图形客户端。')
descriptions=[
'随机密钥加解密后恢复原对象',
'修改密文后认证失败并抛出异常',
'旧序号不能满足下一条消息的预期序号',
'错误HMAC身份标签被拒绝',
'相同登录请求的随机数再次使用被拒绝',
'两条连续帧按顺序独立解析',
'声明9000字节Body被拒，状态为413',
'当前存在的两个EXE的哈希均在现有白名单中',
'密钥位数不少于2048，签名恢复值前后缀符合用例检查',
'未发现gets、strcpy、strcat、system、rand直接调用',
'22个服务端Python文件均可被AST解析',
'默认范围拆为五个互不重叠的200整数子区间',
'Python参考计算与合并得到500500、1000、1、1000',
'2比1得到多数值；2比2返回无多数',
'正确证明通过，仅改总值被拒，自洽错误可通过证明层',
'五次更新后正确节点85分、错误节点0分，并从资格名单排除',
'Header与Body分四段发送，Python端恢复完整对象']
d.table(['编号','检查项','实际观察','结果'],[(f'T{i+1:02d}',t['name'],descriptions[i],'通过' if t['passed'] else '失败') for i,t in enumerate(V['tests'])],[1.2,4.8,9.0,1.4])
d.p('四类运算检查调用的是Python参考运算与合并函数，不是C计算执行；白名单检查仅证明现有EXE哈希匹配，不证明其来自当前源码。危险函数扫描只覆盖指定调用模式，不能替代完整内存安全审计。')
d.page()
d.h('4 关键用例与性能解释')
d.h('4.1 协议与安全复现步骤',2)
d.table(['用例','步骤与预期'],[
('T02密文篡改','构造合法加密信封，改变ciphertext首个十六进制字符；解密接口应拒绝而非输出业务对象。本次符合预期。'),
('T03会话重放','生成sequence=1的信封，以预期1打开成功，再以预期2打开同一信封；应拒绝。本次符合预期。'),
('T05登录重放','使用合法节点、当前时间和新nonce构造身份标签；第一次认证成功，同一请求再次认证被拒。本次符合预期。'),
('T15证明边界','使用四步1275、3775、6275、8775构造根，总值20100通过；仅改总值为20101失败；同时改末步为8776并重建根时证明通过，说明正确性依赖多数。'),
('T17分段发送','使用socketpair将Header和Body分为四次写入，设置接收超时；Python receive_frame应返回ONE、200及对象a=1。本次符合预期。')],[3.5,12.9])
d.h('4.2 误差与安全开销口径',2)
d.p('代码中的准确性误差为 |可信结果−标准答案|/|标准答案|×100%；标准答案为0时使用绝对差直接作为误差值。性能函数以三次累加1至2000000作为基线，另测三次RSA签名及公钥模幂、SHA-256摘要、Merkle根构造和安全消息加解密的耗时，以额外安全耗时/基线计算耗时×100%得到安全开销。')
d.p('该指标是Python微基准，未覆盖实际网络传输、线程排队、界面更新和C客户端执行，也没有完整测量PKCS#1编码的跨端验证流程。历史开销值会随版本、机器负载和样本波动，因此9.32%或11.29%不能作为所有输入与所有环境均不超过30%的保证。本次未重新执行性能基准。')
d.h('4.3 测试覆盖边界',2)
d.p('本次补充了Python端主动分段发送检查，但TCP实际交付可能合并写入，尚未以可控逐字节接收替身穷举全部分片位置。C端长度边界、跨端加解密一致性、任务签名篡改、认证超时、许可证过期、无多数流程和GUI退出重连仍应在完整联调中补测。')
d.page()
d.h('5 问题记录与后续验收')
d.table(['编号与级别','证据及影响','关闭标准'],[
('D01 高','client/network.h有network_connect_retry、network_send_bytes、network_receive_exact声明和调用，当前.c文件无对应定义，阻碍从现有源码完成客户端链接','实现三接口并完成两个EXE清洁构建，验证拆包、粘包和有限重连'),
('D02 高','无多数时finish_task返回false，但_store_result未检查返回值即推进或完成，可能产生缺失子结果','无多数进入明确失败或重试状态，失败任务不得标记正常完成'),
('D03 中','重要任务资格名单生成后，_try_reserve_task未引用名单','重要任务分配时强制资格约束，低信誉节点领取被拒'),
('D04 中','C客户端long参与范围及结果计算，存在32位溢出边界','限制输入及中间值，或改用64位整数并通过边界测试'),
('D05 中','README声称可用的.vscode/tasks.json未找到','恢复启动任务并从新环境复验说明步骤'),
('D06 中','8秒收包超时与业务执行耦合，无独立任务截止和自动补位调度','长耗时计算、节点中断、名额回收及重派均有明确结果')],[2.4,8.6,5.4])
d.h('5.1 建议的最终验收顺序',2)
d.p('先关闭D01并重新签发程序白名单；再以10个不同身份节点完成1至1000的四种运算，保留每轮结果与证明；随后注入1个持续错误节点执行至少5轮，核对错误累计、信誉及真实调度行为；最后执行篡改、重放、断连、无多数和边界输入测试，记录环境及多次性能数据。验收时应保留失败记录及问题关闭证据。')
d.h('5.2 证据索引与最终评价',2)
d.p('历史来源为ENVIRONMENT.md、data/audit.jsonl、data/security_tests.json和data/evaluation.json；实现判据为server/security_tests.py、evaluation.py、task_service.py、merkle.py及client/network.c、network.h、protocol.c。本次17项结果及核对文件SHA-256保存在work/documents/verification.json，可用于复查文档对应的工程快照。')
d.p('最终评价：现有证据可支持课程原型核心算法和部分安全机制有效；本次模块复核17/17通过。由于客户端源码完整性与业务失败路径仍存在明确问题，完整构建、跨端联调及最终验收结论为待完成。')
d.save()
print('created 3 documents')
