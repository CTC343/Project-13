import base64
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = WORK / '交付文件'
items = [
 ('01-overview','01','全流程总览','从开机后的人工启动开始，串起等待连接、在线节点检查、切换任务、并发计算、表决和完成。'),
 ('02-auth-channel','02','认证与安全通信','上半部分是 AUTH → AUTH_OK → 服务端证明校验；下半部分展开每条安全消息如何加密、防篡改、防重放。'),
 ('03-task-compute','03','签名与计算回传','任务分配 → RSA 签名 → 客户端字段检查与验签 → 四段计算 → Merkle 根 → 加密提交结果；包含 wrong / tamper 分支。'),
 ('04-results','04','表决、信誉与审计','区分结果接收与最终可信：先验证和收集，再严格多数表决、合并、更新信誉、生成考核与审计，最后回执和推进轮次。'),
 ('05-lifecycle','05','等待、重连与退出','展开 WAIT / 心跳循环、单次与持续模式、错误处理、主动退出、敏感内存清理，以及独立安全自检。'),
]
diagrams=[]
for slug,number,label,description in items:
    receipt = json.loads((WORK / 'final-review' / slug / (slug+'.finalize-summary.json')).read_text(encoding='utf-8'))
    assert receipt['ok'] and all(v=='pass' for v in receipt['gates'].values()), slug
    raw=(DEST/(slug+'.html')).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==receipt['artifact']['sha256'],slug
    diagrams.append({'id':slug,'number':number,'label':label,'description':description,
                     'html':base64.b64encode(raw).decode('ascii')})

page=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>项目完整流程图</title>
<style>
:root{--bg:#f5f6f4;--paper:#fff;--ink:#20342e;--muted:#65786f;--line:#dbe4df;--accent:#176452;--soft:#e5eee8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:'Segoe UI','Microsoft YaHei',sans-serif;line-height:1.65}.wrap{max-width:1760px;margin:auto;padding:22px 28px 28px}.mast{display:flex;justify-content:space-between;align-items:center;gap:20px}.kicker{font-size:10px;letter-spacing:2px;color:var(--accent);font-weight:700}h1{font-size:27px;margin:2px 0 0;letter-spacing:-.5px}.meta{text-align:right;font-size:12px;color:var(--muted)}.meta a{color:var(--accent);text-decoration:none}.meta a:hover{text-decoration:underline}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 12px;padding-bottom:16px;border-bottom:1px solid var(--line)}.tab{cursor:pointer;font:13px 'Microsoft YaHei',sans-serif;color:var(--muted);background:var(--paper);border:1px solid var(--line);border-radius:7px;padding:10px 15px;transition:background .15s}.tab .number{font:11px Consolas,monospace;margin-right:9px;opacity:.65}.tab:hover{border-color:var(--accent);color:var(--accent)}.tab[aria-selected=true]{color:white;background:var(--accent);border-color:var(--accent)}.context{display:flex;justify-content:space-between;align-items:center;gap:25px;margin-bottom:13px;min-height:34px}#description{font-size:13px;color:var(--muted);margin:0;max-width:1100px}.actions{display:flex;gap:14px;white-space:nowrap}.actions button{border:0;background:none;color:var(--accent);font:12px 'Microsoft YaHei',sans-serif;padding:5px 0;cursor:pointer}.actions button:hover{text-decoration:underline}.frame-shell{background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow:hidden;box-shadow:0 5px 24px #1c453609}iframe{display:block;width:100%;height:calc(100vh - 230px);min-height:640px;border:0;background:var(--paper)}.foot{font-size:12px;color:var(--muted);margin:12px 2px 0}.foot b{font-weight:600;color:var(--accent)}details{font-size:12px;color:var(--muted);margin:17px 0 0;border-top:1px solid var(--line);padding-top:13px}summary{cursor:pointer;user-select:none;color:var(--accent)}.notes{display:grid;grid-template-columns:1fr 1fr;gap:8px 35px;padding:9px 0}.notes p{margin:4px 0}code{font:12px Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere}.source-status{font-size:11px;border-top:1px solid var(--line);padding-top:10px;margin-top:10px}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(prefers-color-scheme:dark){:root{--bg:#101b19;--paper:#16231f;--ink:#dfebe5;--muted:#a1b3aa;--line:#30493d;--accent:#6fd2ac;--soft:#20392e}.tab[aria-selected=true]{background:#206d55;color:#fff;border-color:#206d55}}
@media(max-width:900px){.wrap{padding:18px 15px}.mast{align-items:flex-start}h1{font-size:23px}.tabs{gap:6px}.tab{padding:9px 10px;font-size:12px}.context{display:block}#description{margin-bottom:7px}.actions{justify-content:flex-end}.notes{grid-template-columns:1fr}iframe{height:760px}.meta{font-size:11px}}
</style></head><body><div class="wrap"><header class="mast"><div><div class="kicker">PROJECT 13 / COMPLETE WORKFLOW</div><h1>项目完整流程图</h1></div><div class="meta">依据当前代码 · 2026-11-14<br><a href="开始阅读.html">返回函数阅读手册 ↗</a></div></header>
<div class="tabs" role="tablist" aria-label="流程图章节">__TABS__</div><div class="context"><p id="description"></p><div class="actions"><button id="open">独立查看当前图 ↗</button><button id="download">下载当前图 HTML</button></div></div>
<div class="frame-shell"><iframe id="diagram" title="项目流程图" allow="fullscreen; clipboard-write" allowfullscreen></iframe></div>
<p class="foot"><b>阅读方式：</b>横向看步骤，纵向看处理方；点击节点可查看关联和源码出处。图内可缩放、切换明暗主题、播放流向，并从“导出”菜单保存图片或 SVG。</p>
<details><summary>当前代码的实现边界与阅读说明</summary><div class="notes">
<p>① 从人工打开程序开始，项目没有 Windows 开机自启。等待模式切换到任务模式会重启服务；客户端重连并重新认证。</p>
<p>② 同一连接的后续轮次沿用安全会话。最终总答案显示在服务端；客户端的 <code>ACCEPTED</code> 只确认本次提交。</p>
<p>③ 许可证与程序哈希白名单已经接入认证；RSA 签名保护的是任务，不是 EXE 程序签名。哈希自报不等于硬件远程证明。</p>
<p>④ Merkle 层检查提交内容是否自洽；严格多数依赖诚实节点占多数。无多数时当前代码仍可能推进轮次，没有自动重投。</p>
<p>⑤ 低信誉/恶意节点资格名单目前只被计算，尚未用于实际领取拦截。信誉、轮次与任务集合保存在内存，重启会重建。</p>
<p>⑥ <code>network_connect_retry</code>、<code>network_send_bytes</code>、<code>network_receive_exact</code> 当前只有声明；现有客户端按行收包还可能丢弃换行后的数据。因此流程图不是完整联调通过证明。</p>
<p>⑦ 安全自检是独立功能，共 10 项基础检查；不代表完整渗透测试或无高危漏洞。TEE 未实现；敏感内存清理主要在 C 客户端。</p>
<p>⑧ 图中同时包含正常、等待、错误和演示分支。<code>wrong</code> 会构造自洽错误结果；<code>tamper</code> 会在验签前修改任务，预期被阻断。</p>
</div><p class="source-status">本次只新增说明文件，未修改源码。读取时已有未提交的注释改动：<code>client/network.c</code>、<code>client/protocol.c</code>、<code>client/protocol.h</code>、<code>server/protocol.py</code>。图中来源范围使用已核对的提交版本；上述注释改动不改变所绘流程。</p></details>
<noscript>请启用浏览器 JavaScript 以切换五张离线流程图。</noscript></div>
<script>
const diagrams=__DATA__;
const frame=document.getElementById('diagram');
const buttons=[...document.querySelectorAll('.tab')];
const description=document.getElementById('description');
let active=0;let current='';let blobUrl='';
function choose(index){
 active=index;
 const item=diagrams[index];
 const bytes=Uint8Array.from(atob(item.html),c=>c.charCodeAt(0));
 current=new TextDecoder('utf-8').decode(bytes);
 frame.srcdoc=current;
 frame.title=item.label+' · 项目完整流程图';
 description.textContent=item.description;
 buttons.forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1});
 document.title=item.label+' · 项目完整流程图';
 if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl=''}
}
function url(){if(!blobUrl)blobUrl=URL.createObjectURL(new Blob([current],{type:'text/html;charset=utf-8'}));return blobUrl}
function fromHash(){const id=location.hash.slice(1);const index=diagrams.findIndex(d=>d.id===id);choose(index<0?0:index)}
buttons.forEach((button,index)=>{
 button.addEventListener('click',()=>{if(location.hash.slice(1)===diagrams[index].id)choose(index);else location.hash=diagrams[index].id});
 button.addEventListener('keydown',e=>{if(e.key!=='ArrowRight'&&e.key!=='ArrowLeft')return;e.preventDefault();const i=(index+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;buttons[i].click();buttons[i].focus()});
});
document.getElementById('open').addEventListener('click',()=>window.open(url(),'_blank','noopener'));
document.getElementById('download').addEventListener('click',()=>{const a=document.createElement('a');a.href=url();a.download=diagrams[active].label+'.html';document.body.appendChild(a);a.click();a.remove()});
window.addEventListener('hashchange',fromHash);fromHash();
</script></body></html>'''
tabs=''.join(f'<button class="tab" role="tab" aria-selected="false"><span class="number">{d["number"]}</span>{d["label"]}</button>' for d in diagrams)
page=page.replace('__TABS__',tabs).replace('__DATA__',json.dumps(diagrams,ensure_ascii=False,separators=(',',':')))
(DEST / '项目完整流程图.html').write_text(page,encoding='utf-8')
notes='''# 项目完整流程图

双击同目录的“项目完整流程图.html”。一个文件包含五张图，不需要联网：

1. 全流程总览：人工启动、部署材料、监听连接、在线检查、切换任务、计算、表决与完成。
2. 认证与安全通信：AUTH / AUTH_OK、双向身份证明、会话密钥、加密、防篡改、防重放。
3. 签名与计算回传：任务预留、RSA 签名、公钥验签、四段计算、Merkle 树、RESULT 和演示模式。
4. 表决、信誉与审计：身份与证明检查、收齐结果、严格多数、合并、信誉、失败审计和考核。
5. 等待、重连与退出：心跳、WAIT、单次/持续连接、错误码、退出清理、安全自检。

点击节点可看关联与源码出处；可缩放、切换明暗主题、播放流向及导出图片/SVG。
主页面也可单独打开或下载当前章节。

图按当前代码的调用及分支绘制。需要特别注意：

- 任务启动会重启服务；同连接多轮不需要重新认证。
- ACCEPTED 不等于赢得多数，最终总答案目前只在服务端展示。
- 当前客户端仍有三个网络接口缺少定义，不能把业务图当作完整联调已通过的证明。
- 低信誉名单未接入领取拦截，无多数后仍推进，图中已经注明。
- 开机自启、EXE 程序签名、硬件 TEE 未实现。

本次不修改源码。读取时已有未提交的注释改动：
client/network.c、client/protocol.c、client/protocol.h、server/protocol.py；
这些注释不改变图中流程。源码引用使用已核对的提交版本。
'''
(DEST/'项目流程图说明.md').write_text(notes,encoding='utf-8-sig')

manifest=json.loads((WORK/'source_hashes.json').read_text(encoding='utf-8'))
changed=[p for p,h in manifest.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
assert not changed,changed
print(json.dumps({'package':str(DEST/'项目完整流程图.html'),'diagrams':len(diagrams),'bytes':len(page.encode('utf-8')),'source_unchanged':True},ensure_ascii=False))
