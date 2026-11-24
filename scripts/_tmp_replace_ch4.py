"""Replace Chapter 4 only in the target FINAL_REVIEW DOCX with the new draft."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
DRAFT = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_ch4_resume\CHAPTER_4_NEW_DRAFT.md")
OUT_META = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_ch4_resume\replace_meta.json")
FONT = "TH SarabunPSK"
SIZE = Pt(16)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def set_run_font(run, *, bold: bool | None = None) -> None:
    run.font.name = FONT
    run.font.size = SIZE
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:ascii"), FONT)
    rFonts.set(qn("w:hAnsi"), FONT)
    rFonts.set(qn("w:eastAsia"), FONT)
    if bold is not None:
        run.bold = bold


def add_runs_with_markdown(paragraph: Paragraph, text: str) -> None:
    text = text.replace("`", "")
    parts = re.split(r"(\*\*.+?\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, bold=True)
        else:
            run = paragraph.add_run(part)
            set_run_font(run, bold=False)


def parse_draft(md: str) -> list[dict]:
    lines = md.splitlines()
    blocks: list[dict] = []
    i = 0
    if (
        lines
        and lines[0].startswith("# Chapter 4")
        and len(lines) > 1
        and lines[1].startswith("# Results")
    ):
        blocks.append({"type": "h1", "text": "Chapter 4\nResults and Validation"})
        i = 2
        while i < len(lines) and not lines[i].strip():
            i += 1

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("### "):
            blocks.append({"type": "h3", "text": line[4:].strip()})
            i += 1
            continue
        if line.startswith("## "):
            blocks.append({"type": "h2", "text": line[3:].strip()})
            i += 1
            continue
        if line.startswith("# "):
            blocks.append({"type": "h1", "text": line[2:].strip()})
            i += 1
            continue
        if line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip()
                i += 1
                if re.match(r"^\|[\s\-:|]+\|$", raw):
                    continue
                cells = [c.strip() for c in raw.strip("|").split("|")]
                cells = [re.sub(r"^\*\*(.+)\*\*$", r"\1", c) for c in cells]
                rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append({"type": "ul", "items": items})
            continue
        para_lines = [line.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                break
            if (
                nxt.startswith("#")
                or nxt.startswith("|")
                or nxt.startswith("- ")
            ):
                break
            para_lines.append(nxt.strip())
            i += 1
        blocks.append({"type": "p", "text": " ".join(para_lines)})
    return blocks


def find_ch4_range(doc: Document) -> tuple[int, int]:
    start = end = None
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip().replace("\n", " ")
        style = p.style.name if p.style else ""
        if start is None and style == "Heading 1" and re.search(r"Chapter\s*4\b", t, re.I):
            start = i
        if (
            start is not None
            and i > start + 5
            and style == "Heading 1"
            and re.search(r"Chapter\s*5\b", t, re.I)
        ):
            end = i
            break
    if start is None or end is None:
        raise RuntimeError(f"Chapter range not found start={start} end={end}")
    return start, end


def make_paragraph(doc: Document, text: str, style: str) -> Paragraph:
    new_p = OxmlElement("w:p")
    para = Paragraph(new_p, doc.paragraphs[0]._parent)
    try:
        para.style = style
    except KeyError:
        para.style = "Normal"
    if style.startswith("Heading"):
        run = para.add_run(text)
        set_run_font(run, bold=True)
    else:
        add_runs_with_markdown(para, text)
    return para


def set_cell_text(cell, text: str, *, bold: bool = False) -> None:
    p0 = cell.paragraphs[0]
    for r in p0.runs:
        r.text = ""
    # remove leftover empty runs by rewriting
    for child in list(p0._p):
        if child.tag == qn("w:r"):
            p0._p.remove(child)
    run = p0.add_run(text)
    set_run_font(run, bold=bold)
    for extra in list(cell.paragraphs[1:]):
        extra._element.getparent().remove(extra._element)


def make_table(doc: Document, rows: list[list[str]]) -> Table:
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    try:
        table.style = "Table Grid"
    except KeyError:
        pass
    for ri, row in enumerate(rows):
        for ci in range(ncols):
            val = row[ci] if ci < len(row) else ""
            set_cell_text(table.cell(ri, ci), val, bold=(ri == 0))
    return table


def append_after(prev_el, new_el):
    prev_el.addnext(new_el)
    return new_el


def main() -> None:
    before_hash = sha256(SRC)
    blocks = parse_draft(DRAFT.read_text(encoding="utf-8"))
    n_tables = sum(1 for b in blocks if b["type"] == "table")
    print("BLOCKS", len(blocks), "TABLES", n_tables)

    doc = Document(str(SRC))
    start, end = find_ch4_range(doc)
    print("RANGE", start, end)

    # fingerprints outside chapter
    ch5_text = doc.paragraphs[end].text
    abstract_snip = next(
        (p.text[:60] for p in doc.paragraphs if p.text.startswith("ผลการทดสอบอัตโนมัติ")),
        None,
    )
    ch1_snip = next(
        (
            p.text[:60]
            for p in doc.paragraphs
            if p.style and p.style.name == "Heading 1" and "Chapter 1" in p.text.replace("\n", " ")
        ),
        None,
    )

    ch5_el = doc.paragraphs[end]._p
    to_remove = [doc.paragraphs[i]._p for i in range(start, end)]
    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            parent.remove(el)
    print("REMOVED", len(to_remove))

    # Forward insert: first block before ch5, then chain
    prev = None
    caption_i = 0
    inserted_tables = 0

    def place(el):
        nonlocal prev
        if prev is None:
            ch5_el.addprevious(el)
        else:
            prev.addnext(el)
        prev = el

    for block in blocks:
        if block["type"] in {"h1", "h2", "h3"}:
            style = {"h1": "Heading 1", "h2": "Heading 2", "h3": "Heading 3"}[block["type"]]
            para = make_paragraph(doc, block["text"], style)
            place(para._p)
        elif block["type"] == "p":
            para = make_paragraph(doc, block["text"], "Normal")
            place(para._p)
        elif block["type"] == "ul":
            for item in block["items"]:
                para = make_paragraph(doc, "• " + item, "Normal")
                place(para._p)
        elif block["type"] == "table":
            caption_i += 1
            cap = make_paragraph(
                doc,
                f"Table 4.{caption_i}",
                "Normal",
            )
            # bold caption label
            for r in cap.runs:
                set_run_font(r, bold=True)
            place(cap._p)
            table = make_table(doc, block["rows"])
            # add_table appends at body end — detach and place in chain
            tbl = table._tbl
            if tbl.getparent() is not None:
                tbl.getparent().remove(tbl)
            place(tbl)
            inserted_tables += 1

    doc.save(str(SRC))
    after_hash = sha256(SRC)

    # reopen verify
    check = Document(str(SRC))
    s2, e2 = find_ch4_range(check)
    heads = [
        p.text.strip().replace("\n", " ")[:90]
        for p in check.paragraphs[s2:e2]
        if p.style and p.style.name.startswith("Heading") and p.text.strip()
    ]
    full_ch4 = "\n".join(p.text for p in check.paragraphs[s2:e2])
    markers = {
        "Discussion of Implementation and Validation Results": "Discussion of Implementation and Validation Results"
        in full_ch4,
        "Knowledge Eligibility, Quality, and Approval Status": "Knowledge Eligibility, Quality, and Approval Status"
        in full_ch4,
        "Automated and Focused Software Testing": "Automated and Focused Software Testing" in full_ch4,
        "engineer-ready partial": "engineer-ready partial" in full_ch4,
        "2,107": "2,107" in full_ch4,
        "18/18": "18/18" in full_ch4,
        "730": "730" in full_ch4,
        "Limitations and Discussion of Results": "Limitations and Discussion of Results" in full_ch4,
        "ch5_intact": any(
            "Chapter 5" in p.text.replace("\n", " ")
            for p in check.paragraphs
            if p.style and p.style.name == "Heading 1"
        ),
        "abstract_intact": abstract_snip is not None
        and any(p.text.startswith("ผลการทดสอบอัตโนมัติ") for p in check.paragraphs),
        "ch1_intact": ch1_snip is not None
        and any("Chapter 1" in p.text.replace("\n", " ") for p in check.paragraphs if p.style and p.style.name == "Heading 1"),
    }
    meta = {
        "before_hash": before_hash,
        "after_hash": after_hash,
        "old_range": [start, end],
        "new_range": [s2, e2],
        "tables_inserted": inserted_tables,
        "body_tables_now": len(check.tables),
        "headings": heads,
        "markers": markers,
        "sections": len(check.sections),
        "paragraphs": len(check.paragraphs),
    }
    OUT_META.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
