"""Produce a separate hover edition, leaving the published original intact."""
import base64
import hashlib
import json
import re
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
PROTECTED = json.loads((WORK / 'hover_original_hash.json').read_text(encoding='utf-8'))
ORIGINAL = Path(PROTECTED['path'])
assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == PROTECTED['sha256']
original_text = ORIGINAL.read_text(encoding='utf-8')
start = original_text.index('const diagrams=') + len('const diagrams=')
diagrams, consumed = json.JSONDecoder().raw_decode(original_text[start:])

maps = []
for part in ('hover_server_map.json', 'hover_client_map.json'):
    maps.append(json.loads((WORK / part).read_text(encoding='utf-8-sig')))

plugin_template = (WORK / 'hover_files.js').read_text(encoding='utf-8')
assert plugin_template.count('__SOURCE_MAP__') == 1
checks = WORK / 'hover-check'
checks.mkdir(exist_ok=True)
all_maps = {}
all_files = set()
markdown = ['# 流程图模块与源文件对照', '',
            '对应“项目完整流程图_悬停文件说明版.html”。原版流程图未修改。', '',
            '主要实现表示直接完成该步；调用协作表示流程编排或依赖；接口声明表示头文件中的约定，不等于已有实现。', '']
node_count = row_count = 0

for diagram in diagrams:
    slug = diagram['id']
    spec = json.loads((WORK / (slug + '.json')).read_text(encoding='utf-8'))
    node_ids = {node['id'] for node in spec['nodes']}
    for part in maps:
        assert set(part.get(slug, {})) <= node_ids, (slug, set(part.get(slug, {})) - node_ids)
    file_map = {}
    markdown += ['## ' + diagram['label'], '']
    for node in spec['nodes']:
        entries = {}
        for source in node.get('sources', []):
            entries[source['path']] = {'path':source['path'], 'role':'当前步骤的直接实现或调用入口。', 'kind':'主要实现'}
        for part in maps:
            for entry in part.get(slug, {}).get(node['id'], []):
                assert set(entry) == {'path', 'role', 'kind'}, entry
                assert entry['kind'] in ('主要实现', '调用协作', '接口声明'), entry
                assert entry['role'].strip(), entry
                assert (ROOT / entry['path']).is_file(), entry
                assert entry['path'].startswith(('server/', 'client/')), entry
                entries[entry['path']] = entry
        rank = {'主要实现': 0, '调用协作': 1, '接口声明': 2}
        files = sorted(entries.values(), key=lambda f:(f['path'].split('/')[0], rank[f['kind']], f['path']))
        assert files, (slug, node['id'])
        note = '按本模块实际职责列出主要实现和关键协作文件。'
        if any(f['path'] in ('client/network.c', 'client/network.h') for f in files):
            note += 'network_connect_retry、network_send_bytes、network_receive_exact 当前仅声明；相关调用不等于已完整实现。'
        file_map[node['id']] = {'label':node['label'], 'files':files, 'note':note}
        node_count += 1
        row_count += len(files)
        all_files.update(f['path'] for f in files)
        markdown += ['### ' + node['label'], '', '| 文件 | 参与方式 | 在这里做什么 |', '| --- | --- | --- |']
        for f in files:
            markdown.append('| `' + f['path'] + '` | ' + f['kind'] + ' | ' + f['role'].replace('|', '\\|') + ' |')
        markdown.append('')
    assert set(file_map) == node_ids
    all_maps[slug] = file_map
    raw = base64.b64decode(diagram['html'])
    original_html = raw.decode('utf-8')
    actual_ids = set(re.findall(r'<g\b[^>]*\bdata-node-id="([^"]+)"', original_html))
    assert actual_ids == node_ids, (slug, actual_ids ^ node_ids)
    plugin = plugin_template.replace('__SOURCE_MAP__', json.dumps(file_map, ensure_ascii=False, separators=(',', ':')))
    plugin = plugin.replace('</script', '<\\/script')
    enhanced = original_html.replace('</body>', '<script id="p13-file-hover-extension">\n' + plugin + '\n</script>\n</body>')
    # No node, edge, layout or canonical export scene is rewritten.
    svg = re.compile(r'<svg\b[\s\S]*?</svg>')
    assert svg.findall(enhanced) == svg.findall(original_html), slug
    diagram['html'] = base64.b64encode(enhanced.encode('utf-8')).decode('ascii')
    (checks / (slug+'.html')).write_text(enhanced, encoding='utf-8', newline='')

updated = original_text[:start] + json.dumps(diagrams,ensure_ascii=False,separators=(',',':')) + original_text[start+consumed:]
updated = updated.replace('<title>项目完整流程图</title>', '<title>项目完整流程图 · 悬停文件说明版</title>')
updated = updated.replace('<h1>项目完整流程图</h1>', '<h1>项目完整流程图 · 文件说明版</h1>')
updated = updated.replace('点击节点可查看关联和源码出处。', '鼠标悬停在模块上可看对应的主要文件与作用，提示框可滚动和复制。点击节点仍可查看原有关联。')
updated = updated.replace("item.label+' · 项目完整流程图'", "item.label+' · 悬停文件说明版'")
updated = updated.replace('依据当前代码 · 2026-11-14<br>', '副本增强 · 原版保持不变<br>')
out = WORK / '交付文件' / '项目完整流程图_悬停文件说明版.html'
out.write_text(updated, encoding='utf-8', newline='')
(WORK/'交付文件/流程图模块文件对照.md').write_text('\n'.join(markdown), encoding='utf-8-sig')
(WORK/'hover_merged_map.json').write_text(json.dumps(all_maps,ensure_ascii=False,indent=2), encoding='utf-8')
assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == PROTECTED['sha256']
stats={'diagrams':len(diagrams), 'modules':node_count, 'file_references':row_count,
       'unique_files':len(all_files), 'files':sorted(all_files),
       'additional_bytes':out.stat().st_size-ORIGINAL.stat().st_size, 'original_unchanged':True}
(WORK/'hover_verification.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(stats,ensure_ascii=False))
