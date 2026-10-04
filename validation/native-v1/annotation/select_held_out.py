"""Held-out answers from original OOXML/PDFium and native renders only."""
import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
import pypdfium2 as pdfium
from pypdfium2 import raw as pdfium_c

CORPUS = Path('validation/native-v1')
QA = Path('build/native-v1-heldout-annotation')
assert (CORPUS/'implementation-lock.json').exists()
assert not (CORPUS/'first-run-start.json').exists()
NUMBER = re.compile(r'(?<![A-Za-z0-9])[-−]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)')
targets=[]
def word_table(case, first_row):
    raw=json.loads((QA/case/'independent-word.json').read_text('utf-8'))
    count=0
    for row in raw['tables'][0]['rows'][first_row-1:]:
        for cell in row['cells'][1:]:
            for p in cell['paragraphs']:
                for m in NUMBER.finditer(p['text']):
                    reason='First result table, row-major numeric results after headers; row identifiers are excluded.'
                    if count>=12: reason+=' No measured numerical explanatory prose; continue with the following table results for four prose slots. Test names and significance cutoffs are not measurements.'
                    targets.append({'case':case,'file':'supplement.docx','format':'docx','text':m[0],
                        'value':str(Decimal(m[0].replace(',','').replace('−','-'))),
                        'locator':{'part':'word/document.xml','paragraph':p['paragraph'],'offset':m.start()},
                        'source_cell':{'table':1,'row':row['row'],'physical_cell':cell['cell']},'selection_reason':reason})
                    count+=1
                    if count==16:return
    raise AssertionError('Record target shortfall')

word_table('abstract-quality',2)
word_table('pet-repeatability',3)
def pdf_range(case, number, prefix, count, explanation):
    page=json.loads((QA/case/'independent-pdf.json').read_text('utf-8'))[number-1]
    assert page['text'].count(prefix)==1,prefix
    start=page['text'].index(prefix)
    matches=list(NUMBER.finditer(page['text'],start))[:count]
    assert len(matches)==count
    pdf = pdfium.PdfDocument(str(CORPUS/'papers'/case/'article.pdf'))
    original_page = pdf[number-1]
    textpage = original_page.get_textpage()
    for m in matches:
        indexes=[pdfium_c.FPDFText_GetCharIndexFromTextIndex(textpage, len(page['text'][:i].encode('utf-16-le'))//2) for i in range(m.start(),m.end())]
        assert all(i>=0 for i in indexes)
        chars=[c for c in page['characters'] if c['index'] in indexes]
        assert ''.join(c['text'] for c in chars)==m[0]
        box=[min(c['bbox'][0] for c in chars),min(c['bbox'][1] for c in chars),max(c['bbox'][2] for c in chars),max(c['bbox'][3] for c in chars)]
        targets.append({'case':case,'file':'article.pdf','format':'pdf','text':m[0],
            'value':str(Decimal(m[0].replace(',','').replace('−','-'))),
            'locator':{'page':number,'bbox':box},'selection_reason':explanation})
    textpage.close(); original_page.close(); pdf.close()

pdf_range('abstract-quality',6,'Gynaecology 5 (8.06%)',12,
    'Table 1 reports characteristics of the selected article set in Results. First twelve count/percentage results after headers, excluding categories and table labels.')
pdf_range('abstract-quality',1,'mean OQS of 11.89',4,
    'First numerical result expression in abstract Results: mean, stated confidence level, lower and upper interval bounds; GPT version identifiers are excluded.')
pdf_range('pet-repeatability',5,'Mean (SD) 2.03',12,
    'Table 1: first twelve result tokens in the mean (SD) row; analyst and measurement numbers in headers are identities, not measurements.')
pdf_range('pet-repeatability',2,'were 0.5717 and 0.024',4,
    'First four numerical results in abstract Results: two variance estimates and two variance shares; references and analyst identifiers are excluded.')
assert len(targets)==64
for index,t in enumerate(targets,1):
    t['id']=f'held-{index:03d}'
    t['source_sha256']=hashlib.sha256((CORPUS/'papers'/t['case']/t['file']).read_bytes()).hexdigest()
gold=CORPUS/'held-out-gold.json'
with gold.open('x',encoding='utf-8',newline='\n') as out:
    json.dump({'split':'held-out','annotation':'Developer annotations from independent OOXML/PDFium and Word/Poppler renders after implementation freeze, before PaperDelta scoring. No independent human annotator is claimed.','targets':targets},out,ensure_ascii=False,indent=2)
    out.write('\n')
lock={'locked_at':datetime.now(UTC).isoformat(),'gold_sha256':hashlib.sha256(gold.read_bytes()).hexdigest(),
    'implementation_lock_sha256':hashlib.sha256((CORPUS/'implementation-lock.json').read_bytes()).hexdigest(),
    'annotation_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'targets':64,'shortfall':0,'selection':'Same protocol as development; results not selected or adjusted using PaperDelta output.'}
with (CORPUS/'held-out-gold-lock.json').open('x',encoding='utf-8',newline='\n') as out:
    json.dump(lock,out,indent=2);out.write('\n')
print(json.dumps(lock))
