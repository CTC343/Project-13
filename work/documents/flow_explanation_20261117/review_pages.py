from pathlib import Path
import json
import re
import pypdfium2 as pdfium
import pdfplumber
from docx import Document

root = Path('F:/project13')
work = root/'work/documents/flow_explanation_20261117'
render = work/'render'
pdf_path = render/'review.pdf'
assert pdf_path.exists(), list(render.iterdir())
pdf = pdfium.PdfDocument(str(pdf_path))
for index in range(len(pdf)):
    page = pdf[index]
    bitmap = page.render(scale=1.6)
    im = bitmap.to_pil()
    im.save(render/f'page-{index+1}.png')
    page.close()

with pdfplumber.open(pdf_path) as parsed:
    text = '\n'.join(page.extract_text() or '' for page in parsed.pages)
    page_details=[]
    for i, page in enumerate(parsed.pages):
        body_chars = [c for c in page.chars if c['top'] < page.height-40]
        page_details.append({'page':i+1, 'characters':len(page.chars),
                             'min_x':round(min(c['x0'] for c in body_chars),1),
                             'max_x':round(max(c['x1'] for c in body_chars),1),
                             'min_y':round(min(c['top'] for c in body_chars),1),
                             'max_y':round(max(c['bottom'] for c in body_chars),1)})
steps = [int(v) for v in re.findall(r'第\s*(\d+)\s*步', text)]
assert steps == list(range(1,86)), steps
assert '500500' in text and 'network_receive_exact' in text
assert 'SESSION_TIMEOUT_SECONDS' in text and 'LOGOUT_ACK' in text
assert all(p['min_x'] > 40 and p['max_x'] < 560 for p in page_details)
assert all(p['min_y'] > 45 and p['max_y'] < 800 for p in page_details)
report_path=work/'verification.json'
report=json.loads(report_path.read_text(encoding='utf-8'))
report.update({'preview_renderer':'Microsoft Word PDF export and PDFium PNG rendering',
               'pages':len(pdf), 'pdf_steps_verified':len(steps), 'page_geometry':page_details})
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(work/'review_text.txt').write_text(text,encoding='utf-8')
print(json.dumps({'pages':len(pdf),'steps':len(steps),'geometry':page_details},ensure_ascii=False))
