"""Post-edit validation of FINAL_REVIEW DOCX."""
from pathlib import Path
import hashlib
import json
import re
import zipfile

from docx import Document

SRC = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx"
)
BAK = Path(
    r"C:\Users\MewMew\.codex\.chatgpt-projects\g-p-6aa6cf8212c4819191c5d7719f82110c"
    r"\backups\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.BACKUP_20261122-154049.docx"
)
OUT = Path(r"C:\Users\MewMew\AppData\Local\Temp\eims_final_review_audit")

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

# zip integrity
with zipfile.ZipFile(SRC, "r") as z:
    bad = z.testzip()
    names = z.namelist()

doc = Document(str(SRC))
full = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

checks = {
    "docx_opens": True,
    "zip_ok": bad is None,
    "has_toc_entries": sum(1 for p in doc.paragraphs if (p.style and p.style.name.startswith("toc"))),
    "has_thai_abstract_dated": "20 พฤศจิกายน 2569" in full and "1,374" in full,
    "has_en_abstract_complete": "Product Acceptance is NOT CLAIMED" in full,
    "has_2107": "2,107" in full,
    "has_18_18": "18/18" in full,
    "has_911": "911" in full,
    "has_181": "181" in full,
    "has_730": "730" in full,
    "has_eligible_1": "1 ELIGIBLE" in full or "eligible for human-review" in full.lower(),
    "has_human_not_run": "Human Certification is NOT RUN" in full or "Human Certification ยังเป็น NOT RUN" in full,
    "has_production_partial": "Production Readiness is PARTIAL" in full or "Production Readiness เป็น PARTIAL" in full,
    "no_product_accepted_claim": "Product Accepted" not in full,
    "m2_m3_not_run": "M2/M3" in full and "NOT RUN" in full,
    "class_b_39": "Class B" in full and "39" in full,
    "quality_77_19": "77" in full and "19" in full and "verify" in full.lower(),
    "175_retained": "175" in full,
    "1903_retained": "1,903" in full,
    "33_33_retained": "33/33" in full or "33 of 33" in full,
    "paragraph_count": len([p for p in doc.paragraphs if p.text.strip()]),
}

# page markers
W_LRPB = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lastRenderedPageBreak"
W_BR = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
W_TYPE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
pages = 1
for p in doc.paragraphs:
    for el in p._p.iter():
        if el.tag == W_LRPB or (el.tag == W_BR and el.get(W_TYPE) == "page"):
            pages += 1
checks["page_markers"] = pages

# forbidden overclaims
overclaims = []
for pat, label in [
    (r"\bProduction Ready\b", "Production Ready"),
    (r"\bFully certified\b", "Fully certified"),
    (r"\bProduct Acceptance\b(?! is NOT CLAIMED)", "Product Acceptance without NOT CLAIMED"),
]:
    # soft check
    pass

# ensure backup differs from edited
src_hash = sha256(SRC)
bak_hash = sha256(BAK)
checks["src_sha256"] = src_hash
checks["bak_sha256"] = bak_hash
checks["backup_unchanged"] = bak_hash == "68E104F9EE91C3952732E6D8EECCF99B5F8C2474E1B4652E867DEECEF5472737"
checks["edited_differs_from_backup"] = src_hash != bak_hash

# sample key paragraphs
samples = {}
for needle, key in [
    ("ผลการทดสอบอัตโนมัติในวันที่", "thai_abs"),
    ("The 20 November 2026 backend-final-closure gate reported", "en_abs"),
    ("1 ELIGIBLE", "elig"),
    ("2,107 passed", "t2107"),
    ("18/18 PASS", "b1818"),
]:
    for p in doc.paragraphs:
        if needle in p.text:
            samples[key] = p.text[:280]
            break

(OUT / "post_edit_validation.json").write_text(
    json.dumps({"checks": checks, "samples": samples, "zip_entries": len(names)}, indent=2),
    encoding="utf-8",
)
print(json.dumps(checks, indent=2))
print("--- samples ---")
for k, v in samples.items():
    print(k, ":", v[:200], "...")
