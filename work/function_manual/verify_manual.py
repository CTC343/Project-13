import json
from html.parser import HTMLParser
from pathlib import Path

from build_manual import OUT, WORK


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.sections = []
        self.links = []
        self.external = []
        self.code = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'section' and attrs.get('class') == 'file-section':
            self.sections.append({'id': attrs['id'], 'path': attrs['data-path'],
                                  'count': attrs['data-count'], 'purpose': '', 'cards': []})
        if tag == 'article' and attrs.get('class') == 'function':
            self.sections[-1]['cards'].append({'textContent': ''})
        if tag == 'a':
            self.links.append(attrs['href'])
        for name in ('src', 'href'):
            if attrs.get(name, '').startswith(('http:', 'https:')):
                self.external.append(attrs[name])
        self.stack.append((tag, attrs))
        if tag in ('meta', 'input', 'br'):
            self.stack.pop()

    def handle_endtag(self, tag):
        assert self.stack and self.stack[-1][0] == tag, (tag, self.stack[-3:])
        self.stack.pop()

    def handle_data(self, data):
        if any(t == 'article' for t, a in self.stack):
            self.sections[-1]['cards'][-1]['textContent'] += data
        if self.stack and self.stack[-1][1].get('class') == 'file-purpose':
            self.sections[-1]['purpose'] += data


parser = Inventory()
text = (OUT / '开始阅读.html').read_text(encoding='utf-8')
parser.feed(text)
assert not parser.stack
assert len(parser.sections) == 40
assert sum(len(s['cards']) for s in parser.sections) == 178
assert not parser.external
assert all(link[1:] in {s['id'] for s in parser.sections} | {'home', 'all'} for link in parser.links)
assert len(list((OUT / 'client').glob('*.md'))) == 19
assert len(list((OUT / 'server').glob('*.md'))) == 21
assert not any((OUT / s['path']).exists() for s in parser.sections)
assert not any('client_gui' in s['path'] or s['path'] == 'server/gui.py' for s in parser.sections)
for s in parser.sections:
    md = (OUT / (s['path'] + '.md')).read_text(encoding='utf-8-sig')
    assert md.count('```') == 2 * len(s['cards'])
(WORK / 'ui_inventory.json').write_text(json.dumps(parser.sections, ensure_ascii=False), encoding='utf-8')
print('PASS: 40 documents, 178 entries, links, HTML nesting, offline assets and exclusions')
