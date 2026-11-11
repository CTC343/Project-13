import sys, json, ast, socket, threading, hashlib, datetime
from pathlib import Path
ROOT=Path('F:/project13')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'server'))
import credential_store, rsa_keys
# Keep project credentials, keys, and historical evidence unchanged.
credential_store.provision_demo_credentials=lambda **kwargs: None
rsa_keys.ensure_task_signing_keys=lambda: None
import security_tests as st
from operations import expected_result,merge_values
from task_planner import get_subtask_range
from task_service import choose_majority,update_reputation
from task_state import TaskState
from scheduler import choose_important_task_nodes
from merkle import build_merkle_root,verify_result_proof
from protocol import receive_frame
tests=[]
def check(name,fn):
    try:
        detail=fn()
        tests.append(dict(name=name,passed=True,detail=detail or '通过'))
    except Exception as e:
        tests.append(dict(name=name,passed=False,detail=str(e)))
for name,fn in [('安全会话往返',st.test_encrypted_roundtrip),('密文篡改拦截',st.test_tamper_rejected),('会话序号重放拦截',st.test_replay_rejected),('身份伪造拦截',st.test_identity_spoof_rejected),('登录随机数重放拦截',st.test_auth_replay_rejected),('连续协议帧解析',st.test_sticky_and_fragmented_frames),('超长消息拒绝',st.test_oversized_body_rejected),('现有客户端文件白名单',st.test_executable_allowlist),('RSA任务签名',st.test_rsa_task_signature),('危险函数规则扫描',st.test_no_dangerous_calls)]:
    check(name,fn)
def syntax():
    files=list((ROOT/'server').glob('*.py'))
    for p in files: ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
    return f'{len(files)}个Python模块语法通过'
check('Python服务端语法',syntax)
def ranges():
    got=[get_subtask_range(i) for i in range(1,6)]
    assert got==[(1,200),(201,400),(401,600),(601,800),(801,1000)],got
    return str(got)
check('默认区间拆分',ranges)
def operations():
    for op,want in [('SUM_RANGE',500500),('COUNT_RANGE',1000),('MIN_RANGE',1),('MAX_RANGE',1000)]:
        values=[expected_result(op,*get_subtask_range(i)) for i in range(1,6)]
        assert merge_values(op,values)==want
    return '四类运算的Python参考计算与合并均符合标准答案'
check('四类运算与合并',operations)
def voting():
    assert choose_majority({'a':7,'b':7,'c':8})==7
    assert choose_majority({'a':7,'b':7,'c':8,'d':8}) is None
    return '2比1有多数，2比2无多数'
check('严格多数边界',voting)
def proofs():
    steps=[1275,3775,6275,8775]; root=build_merkle_root(steps)
    assert verify_result_proof('SUM_RANGE',20100,','.join(map(str,steps)),root)
    assert not verify_result_proof('SUM_RANGE',20101,','.join(map(str,steps)),root)
    steps[-1]+=1
    assert verify_result_proof('SUM_RANGE',20101,','.join(map(str,steps)),build_merkle_root(steps))
    return '正确证明通过；仅改总值被拒；自洽错误仍通过证明层，需多数表决'
check('Merkle一致性及边界',proofs)
def reputation():
    state=TaskState()
    for _ in range(5):update_reputation({'good':7,'bad':8},7,state)
    assert state.reputation_scores=={'good':85,'bad':0}
    assert 'bad' in state.malicious_nodes
    assert choose_important_task_nodes(state.reputation_scores,state.malicious_nodes)==['good']
    return '正确节点85分，错误节点0分，第5次错误识别，资格名单排除错误节点'
check('五轮信誉和资格筛选',reputation)
def fragmented():
    left,right=socket.socketpair(); right.settimeout(3)
    def send():
        for part in [b'P13/',b'1 ONE 200 7\n',b'{"a"',b':1}']:
            left.sendall(part)
        left.close()
    t=threading.Thread(target=send);t.start()
    try: assert receive_frame(right)==('ONE',200,{'a':1})
    finally:right.close();t.join()
    return '分四段发送Header与Body，Python接收端正确重组'
check('主动分段发包',fragmented)
records=[json.loads(l) for l in (ROOT/'data/audit.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
sessions={}
for r in records:
    sid=r['task_id'].rsplit('-',1)[0]
    sessions.setdefault(sid,[]).append(r)
summaries=[]
for sid,rs in sessions.items():
    r=rs[-1]
    summaries.append(dict(session=sid,records=len(rs),first=rs[0].get('time'),last=r.get('time'),operation=r.get('operation','未记录'),rounds=[x['round'] for x in rs],trusted=[x.get('trusted_value') for x in rs],integrated=r.get('integrated_result'),nodes=len(r.get('results',{})),malicious=r.get('malicious_nodes'),evaluation=r.get('evaluation')))
source_files=['README.md','PROTOCOL.md','ENVIRONMENT.md','server/config.py','server/protocol.py','server/credential_store.py','server/secure_channel.py','server/task_service.py','server/task_planner.py','server/task_state.py','server/operations.py','server/merkle.py','server/evaluation.py','client/network.c','client/network.h','client/protocol.c','data/audit.jsonl','data/security_tests.json','data/evaluation.json']
report=dict(review_date='2026-11-11',runtime=sys.version.split()[0],tests=tests,history=summaries,historical_security=json.loads((ROOT/'data/security_tests.json').read_text(encoding='utf-8')),current_evaluation=json.loads((ROOT/'data/evaluation.json').read_text(encoding='utf-8')),hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files})
(ROOT/'work/documents/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
