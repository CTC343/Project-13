"""Build an offline, read-only function reference from reviewed metadata."""
from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
OUT = WORK / "项目函数阅读手册_2026-11-14"


def py_inventory(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    result = {}

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result[prefix + child.name] = {
                    "params": [a.arg for a in child.args.posonlyargs + child.args.args]
                    + ([child.args.vararg.arg] if child.args.vararg else [])
                    + [a.arg for a in child.args.kwonlyargs]
                    + ([child.args.kwarg.arg] if child.args.kwarg else []),
                    "signature": ("async " if isinstance(child, ast.AsyncFunctionDef) else "")
                    + "def " + child.name + "(" + ast.unparse(child.args) + "):",
                }
                walk(child, prefix + child.name + ".")
            else:
                walk(child, prefix)

    walk(tree)
    return result


def c_params(args):
    if args.strip() in ("", "void"):
        return []
    names = []
    for arg in args.split(","):
        arg = arg.strip()
        if arg == "...":
            names.append("...")
        else:
            name = re.search(r"([A-Za-z_]\w*)\s*(?:\[[^]]*\])?\s*$", arg)
            assert name, arg
            names.append(name.group(1))
    return names


def validate(files):
    manifest = json.loads((WORK / "source_hashes.json").read_text(encoding="utf-8"))
    assert len(files) == len(manifest), (len(files), len(manifest))
    assert len({f["path"] for f in files}) == len(files)
    assert {f["path"] for f in files} == set(manifest)
    cinv = json.loads((WORK / "c_inventory.json").read_text(encoding="utf-8"))
    count = 0
    param_count = 0
    for file in files:
        path = ROOT / file["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest[file["path"]], path
        expected = py_inventory(path) if path.suffix == ".py" else cinv[file["path"]]
        actual = {f["name"]: f for f in file["functions"]}
        assert len(actual) == len(file["functions"]), f"duplicate: {path}"
        assert set(actual) == set(expected), (path, set(expected) - set(actual), set(actual) - set(expected))
        assert file["purpose"].strip(), path
        for name, func in actual.items():
            spec = expected[name]
            want = spec["params"] if path.suffix == ".py" else c_params(spec["params"])
            have = [p["name"].lstrip("*") for p in func["params"]]
            assert want == have, (path, name, want, have)
            assert func["purpose"].strip(), (path, name)
            assert all(p["description"].strip() for p in func["params"])
            # Canonicalize every displayed signature against the current source.
            func["signature"] = spec["signature"]
            if spec.get("kind"):
                func["kind"] = spec["kind"]
            count += 1
            param_count += len(func["params"])
    return {"files": len(files), "entries": count, "parameters": param_count,
            "client_files": sum(f["path"].startswith("client/") for f in files),
            "server_files": sum(f["path"].startswith("server/") for f in files),
            "source_unchanged": True}


def md_cell(value):
    return value.replace("|", "\\|").replace("\n", "<br>")


def write_markdown(file):
    dest = OUT / (file["path"] + ".md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts = [f"# {file['path']}", "", file["purpose"], ""]
    lang = "python" if file["path"].endswith(".py") else "c"
    if not file["functions"]:
        parts += ["本文件没有自行定义的函数，因此没有函数头和参数可列。", ""]
    for func in file["functions"]:
        suffix = "（回调类型）" if func.get("kind") == "callback" else ""
        parts += [f"## {func['name']}{suffix}", "", f"```{lang}", func["signature"], "```", "",
                  f"**用途：** {func['purpose']}", ""]
        if func["params"]:
            parts += ["| 参数 | 含义 |", "| --- | --- |"]
            parts += [f"| `{p['name']}` | {md_cell(p['description'])} |" for p in func["params"]]
            parts.append("")
        else:
            parts += ["**参数：** 无。", ""]
    dest.write_text("\n".join(parts), encoding="utf-8-sig")


STYLE = r"""
:root{--paper:#f6f5f1;--card:#fff;--ink:#202b32;--muted:#66747c;--line:#dfe4e4;--accent:#186459;--code:#f0f4f3;--sidebar:#edf1ef}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:'Segoe UI','Microsoft YaHei',sans-serif;font-size:15px;line-height:1.75}
aside{position:fixed;inset:0 auto 0 0;width:292px;background:var(--sidebar);border-right:1px solid var(--line);display:flex;flex-direction:column;padding:28px 18px 16px}
.brand{font-size:11px;letter-spacing:2px;color:var(--accent);font-weight:700}.aside-title{font-size:22px;font-weight:700;margin:5px 9px 17px}.brand{margin-left:9px}
.search{width:100%;padding:11px 12px;border:1px solid #c8d4d0;border-radius:8px;background:white;font:inherit;font-size:13px;color:var(--ink);outline:none}.search:focus{border-color:var(--accent);box-shadow:0 0 0 3px #18645918}
.search-hint{font-size:11px;color:var(--muted);margin:6px 5px 14px}nav{overflow:auto;flex:1;padding-right:5px}nav h2{font-size:11px;letter-spacing:1.5px;color:var(--muted);margin:20px 9px 7px;text-transform:uppercase}
.nav-link{display:flex;justify-content:space-between;gap:7px;text-decoration:none;color:#45555c;font-family:Consolas,'Microsoft YaHei',monospace;font-size:13px;padding:6px 9px;border-radius:6px;margin:2px 0}.nav-link:hover{background:#dfe9e4}.nav-link.active{background:var(--accent);color:#fff}.nav-link small{opacity:.65;font-family:'Segoe UI',sans-serif}
.side-footer{font-size:11px;color:var(--muted);border-top:1px solid #d5dfd9;margin-top:14px;padding:12px 9px 0}.all{font-family:inherit;font-weight:600}
main{margin-left:292px;padding:35px 6vw 80px;max-width:1540px}.topbar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:17px;margin-bottom:28px;gap:20px}.eyebrow{font-size:12px;letter-spacing:1px;color:var(--muted)}.tag{font-size:11px;color:var(--accent);background:#e5ede8;border:1px solid #d4e2da;border-radius:20px;padding:3px 12px;white-space:nowrap}
.intro h1{font-size:32px;line-height:1.3;letter-spacing:-.8px;margin:6px 0 14px}.intro p{color:var(--muted);max-width:820px;margin:0 0 20px}.stats{display:flex;gap:30px;margin:25px 0 31px;padding-bottom:25px;border-bottom:1px solid var(--line)}.stat b{display:block;font-size:26px;line-height:1.2;font-weight:650}.stat span{font-size:12px;color:var(--muted)}
.intro-note{background:#eaf0ec;border-left:3px solid var(--accent);padding:13px 17px;border-radius:0 7px 7px 0;font-size:13px;max-width:850px;margin:18px 0 30px}.intro-note p{margin:0;color:#43574f}.file-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.file-tile{display:block;padding:17px 19px;background:var(--card);border:1px solid var(--line);border-radius:9px;text-decoration:none;color:var(--ink)}.file-tile:hover{border-color:var(--accent)}.file-tile b{font-family:Consolas,monospace;font-size:14px;font-weight:600}.file-tile p{font-size:12px;margin:5px 0 0;color:var(--muted);line-height:1.65}.group-title{font-size:17px;margin:30px 0 13px}
.file-section{margin:0 0 48px}.file-heading{display:flex;justify-content:space-between;align-items:baseline;gap:18px;margin-top:8px}.file-heading h1{font-size:29px;margin:0;letter-spacing:-.5px;overflow-wrap:anywhere}.count{font-size:12px;color:var(--muted);white-space:nowrap}.file-purpose{color:var(--muted);max-width:900px;margin:9px 0 28px}.function{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:23px 26px;margin:0 0 19px;scroll-margin-top:24px}.function h2{font-size:17px;line-height:1.5;margin:0 0 13px;font-family:Consolas,'Microsoft YaHei',monospace;overflow-wrap:anywhere}.kind{font:11px 'Microsoft YaHei',sans-serif;color:var(--accent);margin-left:10px;vertical-align:middle}
pre{margin:0 0 16px;padding:15px 17px;background:var(--code);border:1px solid #e2eae5;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.85 Consolas,'Microsoft YaHei',monospace;color:#174b40}code{font-family:Consolas,'Microsoft YaHei',monospace}.purpose{font-size:14px;margin:0 0 18px}.label{color:var(--accent);font-weight:650;margin-right:5px}table{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}th{text-align:left;font-weight:600;background:#fafbf9;color:var(--muted);font-size:12px}th,td{padding:10px 12px;border-bottom:1px solid #e9edeb;vertical-align:top;overflow-wrap:anywhere}th:first-child,td:first-child{width:24%}td:first-child{color:#294d45}tr:last-child td{border-bottom:0}.no-params,.empty{color:var(--muted);font-size:13px;margin:0}.results-heading{font-size:21px;margin:0 0 23px}.empty-state{padding:50px 0;color:var(--muted)}[hidden]{display:none!important}.toolbar-btn{border:1px solid var(--line);background:white;border-radius:6px;color:var(--muted);font:12px 'Microsoft YaHei',sans-serif;padding:6px 10px;cursor:pointer}.toolbar-btn:hover{color:var(--accent);border-color:var(--accent)}
@media(min-width:1500px){main{padding-left:85px;padding-right:85px}}
@media(max-width:850px){aside{width:230px;padding:20px 12px}main{margin-left:230px;padding:26px 25px}.file-grid{grid-template-columns:1fr}.function{padding:20px}.file-heading h1{font-size:24px}}
@media(max-width:600px){aside{position:relative;width:auto;max-height:350px;border-right:0;border-bottom:1px solid var(--line);padding:18px}nav{max-height:160px}.aside-title{margin-bottom:10px}main{margin:0;padding:25px 17px}.side-footer,.search-hint{display:none}.function{padding:17px 14px}.file-heading{display:block}.file-heading h1{font-size:24px}.stats{gap:25px}th:first-child,td:first-child{width:30%}.topbar{margin-bottom:20px}}
@media print{aside,.topbar,.intro,.results-heading,.empty-state{display:none!important}main{margin:0;padding:0;max-width:none}.file-section[hidden],.function[hidden]{display:block!important}.file-section{break-before:page}.function{break-inside:avoid;border-color:#ccc}body{background:#fff;font-size:11px}pre{font-size:10px}table{font-size:10px}.file-heading h1{font-size:22px}}
"""


SCRIPT = r"""
const input=document.getElementById('search');
const sections=[...document.querySelectorAll('.file-section')];
const intro=document.querySelector('.intro');
const results=document.getElementById('results');
const empty=document.getElementById('empty');
const links=[...document.querySelectorAll('.nav-link')];
function show(){
 const query=input.value.trim().toLocaleLowerCase();
 const hash=decodeURIComponent(location.hash.slice(1));
 const all=hash==='all';
 const selected=sections.find(s=>s.id===hash);
 intro.hidden=Boolean(query||all||selected);empty.hidden=true;let hits=0;
 sections.forEach(section=>{
   const fileMatch=(section.dataset.path+' '+section.querySelector('.file-purpose').textContent).toLocaleLowerCase().includes(query);
   let visible=0;
   section.querySelectorAll('.function').forEach(card=>{
     const match=!query||fileMatch||card.textContent.toLocaleLowerCase().includes(query);
     card.hidden=!match;if(match)visible++;
   });
   const noFunctions=section.dataset.count==='0';
   section.hidden=query?!(visible||(noFunctions&&fileMatch)):!(all||section===selected);
   if(!section.hidden)hits+=visible;
 });
 results.hidden=!query;results.textContent=query?'搜索结果 · '+hits+' 条函数 / 声明':'';
 if(query&&!sections.some(s=>!s.hidden))empty.hidden=false;
 links.forEach(a=>a.classList.toggle('active',!query&&a.hash===location.hash));
 document.title=selected&&!query?selected.dataset.path+' · 项目函数阅读手册':'项目函数阅读手册';
}
input.addEventListener('input',show);
document.addEventListener('click',event=>{
 const a=event.target.closest('a[href^="#"]');if(!a)return;
 event.preventDefault();input.value='';
 const target=a.getAttribute('href');
 if(location.hash===target)show();else location.hash=target;
 window.scrollTo({top:0,behavior:'instant'});
});
window.addEventListener('hashchange',show);
document.getElementById('print').addEventListener('click',()=>window.print());
show();
"""


def render_html(files, stats):
    esc = html.escape
    nav = []
    tiles = []
    sections = []
    for group, label in [("client", "客户端 · CLIENT"), ("server", "服务端 · SERVER")]:
        nav.append(f"<h2>{label}</h2>")
        tiles.append(f'<h2 class="group-title">{label}</h2><div class="file-grid">')
        for file in [f for f in files if f["path"].startswith(group + "/")]:
            fid = "f-" + file["path"].replace("/", "-").replace(".", "-")
            path = esc(file["path"])
            count = len(file["functions"])
            nav.append(f'<a class="nav-link" href="#{fid}"><span>{esc(Path(file["path"]).name)}</span><small>{count}</small></a>')
            tiles.append(f'<a class="file-tile" href="#{fid}"><b>{path}</b><p>{esc(file["purpose"])}</p></a>')
            cards = []
            for func in file["functions"]:
                name = esc(func["name"])
                kind = '<span class="kind">回调类型</span>' if func.get("kind") == "callback" else ""
                if func["params"]:
                    rows = "".join(f'<tr><td><code>{esc(p["name"])}</code></td><td>{esc(p["description"])}</td></tr>' for p in func["params"])
                    params = f'<table><thead><tr><th scope="col">参数</th><th scope="col">含义与方向</th></tr></thead><tbody>{rows}</tbody></table>'
                else:
                    params = '<p class="no-params">参数：无。</p>'
                cards.append(f'<article class="function"><h2>{name}{kind}</h2><pre><code>{esc(func["signature"])}</code></pre><p class="purpose"><span class="label">用途</span>{esc(func["purpose"])}</p>{params}</article>')
            if not cards:
                cards.append('<p class="empty">本文件没有自行定义的函数，因此没有函数头和参数可列。</p>')
            sections.append(f'<section class="file-section" id="{fid}" data-path="{path}" data-count="{count}" hidden><div class="file-heading"><h1>{path}</h1><span class="count">{count} 条函数 / 声明</span></div><p class="file-purpose">{esc(file["purpose"])}</p>{"".join(cards)}</section>')
        tiles.append('</div>')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>项目函数阅读手册</title><style>{STYLE}</style></head>
<body><aside><div class="brand">PROJECT 13 / CODE REFERENCE</div><div class="aside-title">函数阅读手册</div><label><span hidden>搜索函数、文件或参数</span><input class="search" id="search" type="search" placeholder="搜索函数、文件或参数…" aria-label="搜索函数、文件或参数"></label><div class="search-hint">例如 security.c、session_key、认证</div><nav aria-label="源码文件目录"><a class="nav-link all" href="#home">阅读首页</a><a class="nav-link all" href="#all">显示全部文件</a>{"".join(nav)}</nav><div class="side-footer">依据当前源码 · 2026-11-14<br>离线可读 · 不包含 GUI 实现</div></aside>
<main><div class="topbar"><span class="eyebrow">客户端 C / 服务端 Python</span><span class="tag">函数头 · 用途 · 参数</span><button class="toolbar-btn" id="print">打印全部</button></div>
<div class="intro"><div class="eyebrow">按你的代码结构，一份文件一份说明</div><h1>从函数开始，读懂项目。</h1><p>点击左侧文件查看函数说明，或直接搜索函数名、参数名和关键词。这里只展示当前源码中的函数头及中文解释，不含函数体。</p>
<div class="stats"><div class="stat"><b>{stats['files']}</b><span>源文件</span></div><div class="stat"><b>{stats['entries']}</b><span>函数 / 声明条目</span></div><div class="stat"><b>{stats['parameters']}</b><span>参数说明</span></div></div>
<div class="intro-note"><p>已排除 client/client_gui.c 与 server/gui.py。C 头文件保留声明，和 .c 文件中同一函数会分别列出；回调类型也有参数说明。没有函数的入口脚本会明确标注。说明以当前实现为准，只有声明、尚缺定义的接口会注明。</p></div>{"".join(tiles)}</div>
<h1 id="results" class="results-heading" hidden></h1><p id="empty" class="empty-state" hidden>没有找到匹配内容。可以换用函数名、文件名或较短的关键词。</p>{"".join(sections)}</main><script>{SCRIPT}</script></body></html>'''


def main():
    files = []
    for filename in ["client.json", "server_core.json", "server_support.json"]:
        files.extend(json.loads((WORK / filename).read_text(encoding="utf-8-sig"))["files"])
    files.sort(key=lambda f: f["path"])
    stats = validate(files)
    OUT.mkdir(parents=True, exist_ok=True)
    for file in files:
        write_markdown(file)
    (OUT / "开始阅读.html").write_text(render_html(files, stats), encoding="utf-8")
    readme = f'''# 项目函数阅读手册

双击 **开始阅读.html**，使用浏览器阅读。无需联网或安装依赖。

- 左侧按 client / server 列出当前源文件，点击查看。
- 搜索框可搜索文件名、函数名、参数名和中文说明。
- client、server 文件夹内为逐文件 Markdown 版本，例如 `client/security.c.md`。
- 每个条目只包含函数头、用途与逐参数说明，不复制函数体。
- 排除 `client/client_gui.c` 与 `server/gui.py`。
- C 头文件声明与 .c 实现分别说明，因此同一函数可能出现两次；回调类型单列。
- Python 的 `self`、默认参数、可变参数与嵌套函数均按源码列出。
- demo.py、provision.py 没有自行定义的函数，说明页只交代入口职责。
- 这些是说明文件，不是可替换源代码，也不需要运行或编译。

当前版本：2026-11-14。
覆盖 {stats['client_files']} 个客户端文件、{stats['server_files']} 个服务端文件，
共 {stats['entries']} 条函数 / 声明、{stats['parameters']} 项参数说明。
已逐文件核对函数和参数清单；生成前后检查源文件内容未变化。
'''
    (OUT / "阅读说明.md").write_text(readme, encoding="utf-8-sig")
    # Recheck after all rendering as well as before it.
    validate(files)
    (WORK / "verification.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(OUT), **stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
