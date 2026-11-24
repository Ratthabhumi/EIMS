from pypdf import PdfReader
from docx import Document

r = PdfReader(
    r"C:\Users\MewMew\AppData\Local\Temp\eims_final_review_audit\abstract_render\abstract_only.pdf"
)
for i, p in enumerate(r.pages):
    t = p.extract_text() or ""
    print("PAGE", i + 1)
    print("  has_kw_thai", "คำสำคัญ" in t)
    print("  has_keywords", "Keywords" in t)
    print("  has_NOT_CLAIMED", "NOT CLAIMED" in t)
    print("  has_กล่าวอ้าง", "กล่าวอ้าง" in t)
    print("  has_PARTIAL", "PARTIAL" in t)
    print("  last_180:", repr(t.strip()[-180:] if t.strip() else ""))
    print()

doc = Document(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
W_BR = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
W_TYPE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
W_SECT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr"
for i in range(28, 50):
    p = doc.paragraphs[i]
    breaks = []
    for el in p._p.iter():
        if el.tag == W_BR and el.get(W_TYPE) == "page":
            breaks.append("page")
        if el.tag == W_SECT:
            breaks.append("sectPr")
    pb = p.paragraph_format.page_break_before
    t = p.text.strip()[:70].replace("\n", " ")
    if t or breaks or pb:
        print(
            f"{i}: pb_before={pb} breaks={breaks} style={p.style.name} text={t!r}"
        )
