# Canva Presentation Change Plan (manual / after MCP auth)

**Design:** https://www.canva.com/design/DAHYXQN-j8k/lg-rK6VVoNG4ErShtP-uQA/edit  
**Session status:** Canva MCP authentication was **rejected** by the user — Cursor did **not** edit Canva.  
**Instruction:** Inspect live page count (previously observed 25 pages vs “19 slides” title) **before** deleting/reordering pages. Preserve accepted narrative; apply only corrections below.

## Page-level corrections (content, not redesign)

| Topic | Keep | Change / add Presenter Note |
|---|---|---|
| Catalog totals | Show 911 inventory | State 181 = Analyzer-matchable subset (exact `catalog_id` subset); 730 = other governed; **never sum** |
| 175 | If present | Label **historical Gate H snapshot**, not a third live catalog |
| Class B 39 | If present | Classification metric = 28+11; **not** a catalog total |
| Product dropdown | If screenshot | Must say **All Analyzer products (181)**, not “All products” |
| Eligible / Approved | 1 / 0 | Eligible ≠ human-approved; Human Certification NOT RUN |
| Knowledge quality | Optional new note | 77/911 partial engineer-ready; 19/911 full verify chain (2026-11-22 audit) |
| Test scores | If 1374 / 1903 / 2107 / 18/18 / 33/33 appear | Keep as **dated** historical layers; do not merge into one “latest” score |
| Engineering PASS | OK | Note **inherited**; handover did not re-run suite |
| Production / Product Acceptance | — | PARTIAL / NOT CLAIMED |
| Verify slide | — | Fix applied ≠ Resolved; needs post-remediation evidence + reviewer |

## Presenter Notes to paste (shared)

> EIMS helps engineers investigate with evidence — not claim certainty. Catalog: 911 governed inventory; 181 Analyzer-matchable subset; 730 outside Analyzer loader. Class B 39 is a certification class, not another catalog. Eligible ASA 113005 is ready for human review; human-approved remains 0. Knowledge quality audit: only 19 of 911 rows have a full verify chain — we invest in verification quality next, not raw row count.

## Export

After Canva preview approval: export **PDF 16:9** for print. Until then PDF remains **NOT VERIFIED** in the repo package.
