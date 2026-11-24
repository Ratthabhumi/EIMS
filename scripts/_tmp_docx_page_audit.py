"""Page-aware extract + contested claim dump for FINAL_REVIEW DOCX."""
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

W_BR = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
W_TYPE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
W_LRPB = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lastRenderedPageBreak"
W_TBL = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl"
W_P = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
W_T = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
W_SECT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sectPr"

# Walk body in document order; track page via lastRenderedPageBreak
pages = {1: []}
page = 1
body = doc.element.body
tbl_count = 0
for child in body.iterchildren():
    # count page breaks inside this block before content
    breaks_before = 0
    texts = []
    if child.tag == W_P:
        for el in child.iter():
            if el.tag == W_LRPB:
                breaks_before += 1
            elif el.tag == W_BR and el.get(W_TYPE) == "page":
                breaks_before += 1
            elif el.tag == W_T and el.text:
                texts.append(el.text)
        style = ""
        # try style via python-docx mapping is hard; skip
        text = "".join(texts).strip()
        for _ in range(breaks_before):
            page += 1
            pages.setdefault(page, [])
        if text:
            pages[page].append({"kind": "p", "text": text})
    elif child.tag == W_TBL:
        tbl_count += 1
        rows = []
        for tr in child.findall(
            ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"
        ):
            cells = []
            for tc in tr.findall(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"
            ):
                cell_text = "".join(
                    t.text or ""
                    for t in tc.iter(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
                    )
                ).strip()
                cells.append(cell_text)
            rows.append(cells)
            # page breaks in table cells
            for el in tr.iter():
                if el.tag == W_LRPB or (
                    el.tag == W_BR and el.get(W_TYPE) == "page"
                ):
                    page += 1
                    pages.setdefault(page, [])
        pages[page].append({"kind": "table", "ti": tbl_count, "rows": rows})

# Also check headers/footers for page fields
sect_count = len(list(body.iter(W_SECT)))

# Contested claim scan with page
contested_re = re.compile(
    r"(1,?374|1,?903|2,?107|\b175\b|\b181\b|\b911\b|\b730\b|33\s*/\s*33|"
    r"18\s*/\s*18|eligib|human[- ]?approv|Human Certification|NOT RUN|"
    r"[Pp]roduction [Rr]ead(?:y|iness)|Fully functioning|Production Ready|"
    r"[Pp]roduct [Aa]ccept|77\s*/\s*911|19\s*/\s*911|Class B|"
    r"Gate[- ]?[A-H]|Engineering Acceptance|Browser Acceptance|"
    r"PASS|PARTIAL|NOT CLAIMED|fully certified|Robust)",
    re.I,
)

claims = []
for pg, items in pages.items():
    for item in items:
        if item["kind"] == "p":
            if contested_re.search(item["text"]):
                claims.append({"page": pg, "kind": "p", "text": item["text"][:400]})
        else:
            flat = " || ".join(" | ".join(r) for r in item["rows"])
            if contested_re.search(flat):
                claims.append(
                    {
                        "page": pg,
                        "kind": "table",
                        "ti": item["ti"],
                        "text": flat[:500],
                    }
                )

summary = {
    "total_pages_estimated": page,
    "body_tables": tbl_count,
    "sectPr_count": sect_count,
    "items_per_page": {str(k): len(v) for k, v in pages.items()},
    "contested_claim_count": len(claims),
}
(out / "pages_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
(out / "contested_by_page.json").write_text(
    json.dumps(claims, ensure_ascii=False, indent=2), encoding="utf-8"
)
# full page text for audit
page_texts = {}
for pg, items in pages.items():
    lines = []
    for item in items:
        if item["kind"] == "p":
            lines.append(item["text"])
        else:
            lines.append(f"[TABLE {item['ti']}]")
            for r in item["rows"]:
                lines.append(" | ".join(r))
    page_texts[str(pg)] = "\n".join(lines)
(out / "pages_text.json").write_text(
    json.dumps(page_texts, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, indent=2))
print("--- contested sample ---")
for c in claims[:40]:
    print(f"p{c['page']}\t{c['kind']}\t{c['text'][:160]}")
print(f"... total contested {len(claims)}")
