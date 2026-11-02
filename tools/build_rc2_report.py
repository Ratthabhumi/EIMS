"""Build a new staged DOCX from existing report sources, preserving history."""
from pathlib import Path
import re,json,hashlib
from docx import Document
from docx.shared import Inches,Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
root=Path(__file__).resolve().parents[1]
out=root/'docs/delivery/rc2-20261101';out.mkdir(parents=True,exist_ok=True)
doc=Document(); sec=doc.sections[0];sec.top_margin=sec.bottom_margin=Inches(.8);sec.left_margin=sec.right_margin=Inches(.85)
for name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
 st=doc.styles[name];st.font.name='Calibri';st.font.size=Pt(11 if name=='Normal' else 24 if name=='Title' else 16 if name=='Heading 1' else 13)
 st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Leelawadee UI');st.font.color.rgb=__import__('docx').shared.RGBColor(0,0,0)
for st in doc.styles:
 for border in list(st.element.iter(qn('w:pBdr'))):border.getparent().remove(border)
normal=doc.styles['Normal'].paragraph_format;normal.space_after=Pt(6);normal.line_spacing=1.12
sec.header.paragraphs[0].text='EIMS    Academic staging copy    1 November 2026'
f=sec.footer.paragraphs[0];f.text='Draft for author review     Page ';fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');f._p.append(fld)
doc.add_paragraph('EIMS graduation report',style='Title')
doc.add_paragraph('Evidence grounded multi vendor log investigation')
doc.add_paragraph('Ratthabhumi Peansukmanee\nComputer Engineering International Program\nKing Mongkut’s Institute of Technology Ladkrabang\nAcademic year 2026')
doc.add_paragraph('Staged assembly for author and institutional review. This copy preserves current graduation revisions and explicitly marked historical prototype chapters. It is not an approved thesis or a production certification.')
doc.add_heading('Evidence and publication boundaries',1)
doc.add_paragraph('Analyzer publication baseline 2a0d903: 391 engineering tests. Verification baseline 7335aa2: 394 engineering tests, CI 41308596046. RC2 changes only the shared investigation presentation and delivery artifacts; final source SHA and CI are recorded in PR #10 and the staging manifest. Scientific baseline remains a7b5291: 12 DRAFT DEV, 61 claims, zero genuine human review. Diagnostic accuracy is NOT_MEASURED.')
doc.add_paragraph('HTTPS browser acceptance remains blocked by authorization. Physical USB and production are not tested. The September observations do not certify this release. Institutional cover, approval/signature pages and author biography require owner-supplied forms; no signatures or approval are invented. Mermaid diagrams are preserved as source listings pending author conversion to approved figures.')
doc.add_page_break();doc.add_heading('Contents',1)
toc=OxmlElement('w:fldSimple');toc.set(qn('w:instr'),'TOC \\o "1-3" \\h \\z \\u');doc.add_paragraph()._p.append(toc)
paths=[root/'docs/report'/n for n in ['ABSTRACT_TH.md','ABSTRACT_EN.md','ACKNOWLEDGMENTS.md','CHAPTER_1_INTRODUCTION.md','CHAPTER_2_CONCEPTS_AND_RELATED_TECHNOLOGIES.md','CHAPTER_3_SYSTEM_DESIGN_AND_IMPLEMENTATION.md','CHAPTER_4_RESULTS_AND_VALIDATION.md','CHAPTER_5_SUMMARY_AND_RECOMMENDATIONS.md','REFERENCES.md']]
def clean(s):
 s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1 (\2)',s)
 return s.replace('**','').replace('`','').strip()
for p in paths:
 source_label=doc.add_paragraph('Source '+p.relative_to(root).as_posix(),style='Caption');source_label.paragraph_format.page_break_before=True
 text=p.read_text(encoding='utf-8'); lines=text.splitlines(); i=0;code=False
 while i<len(lines):
  line=lines[i].strip();i+=1
  if line.startswith('```'):
   code=not code
   if code: doc.add_paragraph('Source listing '+line[3:],style='Caption')
   continue
  if not line or line=='---':continue
  if code:
   para=doc.add_paragraph(line);para.paragraph_format.space_after=Pt(0)
   for r in para.runs:r.font.name='Consolas';r.font.size=Pt(8)
  elif line.startswith('|'):
   tablelines=[line]
   while i<len(lines) and lines[i].strip().startswith('|'):tablelines.append(lines[i].strip());i+=1
   data=[[clean(c) for c in l.strip('|').split('|')] for l in tablelines if not re.fullmatch(r'[\s|:\-]+',l)]
   cols=max(map(len,data));t=doc.add_table(rows=0,cols=cols);t.style='Light Shading Accent 1'
   for vals in data:
    cells=t.add_row().cells
    for k,v in enumerate(vals):cells[k].text=v
   for r in t.rows:
    for cell in r.cells:
     for para in cell.paragraphs:
      for run in para.runs:run.font.size=Pt(9)
  elif line.startswith('#'):
   level=min(len(line)-len(line.lstrip('#')),3);doc.add_heading(clean(line.lstrip('#')),level)
  else:doc.add_paragraph(clean(line.lstrip('> ')))
path=out/'EIMS_RC2_REPORT_REVIEW.docx'
if path.exists():raise FileExistsError(path)
doc.save(path)
(out/'source_manifest.json').write_text(json.dumps({'status':'STAGED_PENDING_VISUAL_AND_OWNER_REVIEW','generator':'tools/build_rc2_report.py','sources':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'historical_binaries_overwritten':False},indent=2)+'\n')
print(path)
