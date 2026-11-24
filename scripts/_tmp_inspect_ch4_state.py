"""Inspect whether Chapter 4 in target DOCX matches the new draft."""
from docx import Document
from pathlib import Path
import hashlib
import json
import re

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
BAK = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\backups\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.BACKUP_20261122-160118.docx"
)
DRAFT = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\audit_work\snapshot\docs\report\CHAPTER_4_RESULTS_AND_VALIDATION.md"
)
OUT = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_ch4_resume")
OUT.mkdir(exist_ok=True)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


def find_heading_idx(doc: Document, needles: list[str]) -> list[tuple[int, str, str]]:
    hits = []
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip().replace("\n", " ")
        style = p.style.name if p.style else ""
        for n in needles:
            if n.lower() in t.lower():
                hits.append((i, style, t[:120]))
                break
    return hits


def chapter_range(doc: Document):
    start = end = None
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip().replace("\n", " ")
        style = p.style.name if p.style else ""
        # Chapter 4 heading variants
        if start is None and (
            (style.startswith("Heading") and re.match(r"^Chapter\s*4\b", t, re.I))
            or t in ("Chapter 4", "Chapter 4 Results and Validation")
            or re.match(r"^Chapter\s*4\s*$", t, re.I)
            or (style == "Heading 1" and "Results and Validation" in t and i > 500)
        ):
            # Prefer explicit Chapter 4
            if re.search(r"Chapter\s*4", t, re.I) or (
                style == "Heading 1" and t.startswith("Results")
            ):
                if re.search(r"Chapter\s*4", t, re.I) or (
                    i > 0
                    and "Chapter 4" in doc.paragraphs[i - 1].text.replace("\n", " ")
                ):
                    start = i if re.search(r"Chapter\s*4", t, re.I) else i - 1
        if start is not None and end is None and i > start + 5:
            if style == "Heading 1" and re.search(r"Chapter\s*5", t, re.I):
                end = i
                break
            if t.startswith("Chapter 5"):
                end = i
                break
    return start, end


doc = Document(str(SRC))
bak = Document(str(BAK))

# Find Chapter 4 / 5 in current
ch4_hits = find_heading_idx(
    doc,
    [
        "Chapter 4",
        "4.1 Overview",
        "4.3.1 Overview of the Knowledge Inventory",
        "4.6 Discussion of Implementation",
        "4.6 Limitations and Discussion",
        "engineer-ready partial",
        "2,107",
        "18/18",
        "730",
        "Gate H",
        "Chapter 5",
    ],
)

start, end = chapter_range(doc)
print("CURRENT_PARAS", len(doc.paragraphs))
print("CH4_RANGE", start, end)
print("TABLES", len(doc.tables))

# Marker probes for NEW draft vs OLD chapter
markers_new = [
    "engineer-ready partial",
    "Discussion of Implementation and Validation Results",
    "Complete inventory across the examined knowledge categories",
    "Certification Class B is a separate classification",
    "completed-code certification regression",
    "DEFAULT_ANALYZE_MAX",
]
markers_old = [
    "Limitations and Discussion of Results",
    "Research Evaluation Limitations",
    "latest working-tree inventory examined during the evidence audit",
    "Passed: 1,903 tests.",
]

full = "\n".join(p.text for p in doc.paragraphs)
print("NEW_MARKERS", {m: (m in full) for m in markers_new})
print("OLD_MARKERS", {m: (m in full) for m in markers_old})

# Compare Ch4 text lengths if range found
if start is not None and end is not None:
    ch4_paras = [p.text.strip() for p in doc.paragraphs[start:end] if p.text.strip()]
    print("CH4_NONEMPTY_PARAS", len(ch4_paras))
    print("CH4_FIRST", ch4_paras[0][:80] if ch4_paras else None)
    print("CH4_LAST", ch4_paras[-1][:80] if ch4_paras else None)
    # headings in range
    heads = [
        (i, p.style.name, p.text.strip()[:80].replace("\n", " "))
        for i, p in enumerate(doc.paragraphs[start:end], start=start)
        if p.style and p.style.name.startswith("Heading") and p.text.strip()
    ]
    print("CH4_HEADINGS", len(heads))
    for h in heads[:40]:
        print(" ", h)

# Backup abstract vs current (outside ch4 should mostly match except TOC)
bak_full = "\n".join(p.text for p in bak.paragraphs)
print("BAK_HAS_NEW", any(m in bak_full for m in markers_new[:3]))
print("BAK_HAS_OLD_LIM", "Limitations and Discussion of Results" in bak_full)
print("SRC_HASH", sha(SRC))
print("BAK_HASH", sha(BAK))
print("DRAFT_EXISTS", DRAFT.exists(), "LEN", DRAFT.stat().st_size if DRAFT.exists() else 0)

# Sample distinctive sentences around 4.1
for i, p in enumerate(doc.paragraphs):
    if "4.1 Overview of Implementation Results" in p.text:
        print("FOUND_41_AT", i)
        for j in range(i, min(i + 8, len(doc.paragraphs))):
            t = doc.paragraphs[j].text.strip()
            if t:
                print(f"  [{j}] {t[:140]}")
        break

(OUT / "ch4_probe.json").write_text(
    json.dumps(
        {
            "start": start,
            "end": end,
            "tables": len(doc.tables),
            "new_markers": {m: (m in full) for m in markers_new},
            "old_markers": {m: (m in full) for m in markers_old},
            "src_hash": sha(SRC),
            "bak_hash": sha(BAK),
        },
        indent=2,
    ),
    encoding="utf-8",
)
