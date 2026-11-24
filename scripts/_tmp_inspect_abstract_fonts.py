"""Inspect abstract section fonts and paragraph indices."""
from docx import Document
from docx.shared import Pt, Twips
from pathlib import Path

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
doc = Document(str(SRC))

# Print first ~50 non-empty paragraphs with font info
count = 0
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if not t:
        continue
    count += 1
    if count > 25:
        break
    style = p.style.name if p.style else ""
    pf = p.paragraph_format
    print(f"=== {i} style={style!r} ===")
    print(f"  space_before={pf.space_before} space_after={pf.space_after} line_spacing={pf.line_spacing}")
    print(f"  text[:120]={t[:120]!r}")
    for j, r in enumerate(p.runs[:6]):
        f = r.font
        print(
            f"  run{j}: font={f.name!r} size={f.size} bold={f.bold} "
            f"len={len(r.text)} sample={r.text[:40]!r}"
        )
    # style font
    try:
        sf = p.style.font
        print(f"  style_font={sf.name!r} size={sf.size} bold={sf.bold}")
    except Exception as e:
        print(f"  style_font_err={e}")
