from docx import Document
from pathlib import Path
import json
import re

path = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
out = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_final_review_audit")
out.mkdir(exist_ok=True)
doc = Document(str(path))

paras = []
for i, p in enumerate(doc.paragraphs):
    style = p.style.name if p.style else ""
    text = p.text.strip()
    if not text:
        continue
    paras.append({"i": i, "style": style, "text": text})

page_breaks = 0
W_BR = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
W_TYPE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
W_LRPB = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lastRenderedPageBreak"
for p in doc.paragraphs:
    for el in p._p.iter():
        if el.tag == W_BR and el.get(W_TYPE) == "page":
            page_breaks += 1
        elif el.tag == W_LRPB:
            page_breaks += 1

tables = []
for ti, table in enumerate(doc.tables):
    rows = []
    for row in table.rows:
        rows.append([c.text.strip().replace("\n", " | ") for c in row.cells])
    tables.append(
        {
            "ti": ti,
            "rows": rows[:60],
            "nrows": len(table.rows),
            "ncols": len(table.columns),
        }
    )

patterns = {
    "1374": r"1,?374",
    "1903": r"1,?903",
    "2107": r"2,?107",
    "175": r"\b175\b",
    "181": r"\b181\b",
    "911": r"\b911\b",
    "730": r"\b730\b",
    "33/33": r"33\s*/\s*33",
    "18/18": r"18\s*/\s*18",
    "eligible": r"eligib",
    "human_cert": r"human[- ]?approv|Human Certification|NOT RUN|eligible",
    "production": r"[Pp]roduction [Rr]ead(y|iness)|Fully functioning|Production Ready|FULLY",
    "product_accept": r"[Pp]roduct [Aa]ccept",
    "77/911": r"77\s*/\s*911",
    "19/911": r"19\s*/\s*911",
    "ClassB": r"Class B|\b39\b|\b28\b|\b11\b",
    "Gate": r"Gate[- ]?[A-H]|Engineering Acceptance|Browser Acceptance",
}

hits = {k: [] for k in patterns}
for p in paras:
    for k, pat in patterns.items():
        if re.search(pat, p["text"], re.I):
            hits[k].append(
                {"i": p["i"], "style": p["style"], "text": p["text"][:300]}
            )

(out / "paras.json").write_text(
    json.dumps(paras, ensure_ascii=False, indent=2), encoding="utf-8"
)
(out / "tables.json").write_text(
    json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8"
)
(out / "hits.json").write_text(
    json.dumps({k: v[:40] for k, v in hits.items()}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("paras", len(paras), "tables", len(tables), "page_break_markers", page_breaks)
print("hit_counts", {k: len(v) for k, v in hits.items()})

heads = [
    p
    for p in paras
    if p["style"].startswith("Heading")
    or p["style"] in ("Title", "Subtitle")
    or re.match(
        r"^(Chapter|ABSTRACT|บท|CHAPTER|Conclusion|Future|Results|Discussion)",
        p["text"],
        re.I,
    )
]
print("heads", len(heads))
for h in heads:
    print(f"{h['i']}\t{h['style']}\t{h['text'][:120]}")
