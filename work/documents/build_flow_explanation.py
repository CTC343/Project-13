from pathlib import Path
import re
import json
import hashlib
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path('F:/project13')
WORK = ROOT / 'work/documents/flow_explanation_20261117'
WORK.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'work/documents/项目完整运行流程逐步讲解.md'
OUT = ROOT / '项目完整运行流程逐步讲解.docx'
content = SOURCE.read_text(encoding='utf-8')
steps = [int(x) for x in re.findall(r'^【(\d+)】', content, re.M)]
assert steps == list(range(1, 86)), steps

doc = Document()
section = doc.sections[0]
section.page_width = Cm(21)
section.page_height = Cm(29.7)
section.top_margin = Cm(2.0)
section.bottom_margin = Cm(1.9)
section.left_margin = Cm(2.15)
section.right_margin = Cm(2.15)
section.footer_distance = Cm(0.9)

for name, size, east, bold in [('Normal', 11, '宋体', False),
                                ('Title', 23, '黑体', True),
                                ('Subtitle', 11, '宋体', False),
                                ('Heading 1', 15, '黑体', True),
                                ('Heading 2', 12, '黑体', True)]:
    st = doc.styles[name]
    st.font.name = 'Arial'
    st.font.size = Pt(size)
    st.font.bold = bold
    st.font.color.rgb = RGBColor(0, 0, 0)
    fonts = st.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn('w:eastAsia'), east)
    fonts.set(qn('w:ascii'), 'Arial')
    fonts.set(qn('w:hAnsi'), 'Arial')
    for key in ['asciiTheme', 'hAnsiTheme', 'eastAsiaTheme', 'cstheme', 'csTheme']:
        fonts.attrib.pop(qn('w:' + key), None)
    fmt = st.paragraph_format
    fmt.line_spacing = 1.24
    fmt.space_after = Pt(7)
    fmt.widow_control = True
    if name.startswith('Heading'):
        fmt.keep_with_next = True
        fmt.keep_together = True
        fmt.space_before = Pt(14 if name == 'Heading 1' else 9)
        fmt.space_after = Pt(7)
    if name == 'Title':
        fmt.space_before = Pt(4)
        fmt.space_after = Pt(10)
        fmt.keep_with_next = True

paras = [p.strip() for p in content.split('\n\n') if p.strip()]
for i, text in enumerate(paras):
    if text.startswith('# '):
        p = doc.add_paragraph(text[2:], 'Title')
    elif text.startswith('## '):
        p = doc.add_paragraph(text[3:], 'Heading 1')
    elif text.startswith('### '):
        p = doc.add_paragraph(text[4:], 'Heading 2')
    elif i == 1:
        p = doc.add_paragraph(text, 'Subtitle')
    elif re.match(r'^【\d+】', text):
        p = doc.add_paragraph()
        number, rest = re.match(r'^【(\d+)】(.*)$', text, re.S).groups()
        p.add_run(f'第 {int(number):02d} 步  ').bold = True
        p.add_run(rest)
    else:
        p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer.add_run('第 ')
run.font.size = Pt(9)
field = OxmlElement('w:fldSimple')
field.set(qn('w:instr'), 'PAGE')
footer._p.append(field)
run = footer.add_run(' 页')
run.font.size = Pt(9)

for root in [doc.styles.element, doc.element]:
    for border in list(root.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    for colors in root.iter(qn('w:color')):
        colors.attrib.pop(qn('w:themeColor'), None)
        colors.attrib.pop(qn('w:themeTint'), None)
        colors.attrib.pop(qn('w:themeShade'), None)
        colors.set(qn('w:val'), '000000')

doc.core_properties.title = '分布式计算项目完整运行流程逐步讲解'
doc.core_properties.subject = '项目13 启动认证加密计算验证与异常分支'
doc.core_properties.author = ''
doc.core_properties.keywords = 'P13 RSA SHA-256 HMAC Merkle'
doc.save(OUT)

saved = Document(OUT)
assert len(saved.paragraphs) == len(paras)
assert sum(bool(re.match(r'^第 \d+ 步', p.text)) for p in saved.paragraphs) == 85
assert all(p.text for p in saved.paragraphs)
files = list((ROOT/'server').glob('*.py')) + list((ROOT/'client').glob('*.c')) + list((ROOT/'client').glob('*.h'))
sources = [{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
report = {'output': str(OUT), 'steps': len(steps), 'paragraphs': len(paras),
          'source_characters': len(content), 'bytes': OUT.stat().st_size, 'sources': sources}
(WORK/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='sources'}, ensure_ascii=False))
