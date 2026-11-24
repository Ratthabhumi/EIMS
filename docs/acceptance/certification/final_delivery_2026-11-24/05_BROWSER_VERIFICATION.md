# Browser Verification — Knowledge Catalog (post UI change)

**Date:** 2026-11-22  
**Portal:** `http://127.0.0.1:3001` (left running; not restarted)  
**API:** `http://127.0.0.1:8031` (**restarted** this pass to load Unified Catalog routes; disposable DB `eims_cursor_accept` @ `56470`)

## Result: **PASS** (Catalog UI + live API agreement)

| Check | Observed |
|---|---|
| Tab | Knowledge Catalog **(911)** |
| Subtitle | Showing **1 of 911** on Eligible facet; Analyzer-matchable **181**; Class B **39**; Eligible **1**; Human-approved **0** |
| KPI cards | Governed **911** · Analyzer-matchable **181** · Other governed **730** · Eligible/Approved **1 / 0** |
| Facets | Analyzer-matchable (181) · All governed (911) · Class B (39) · Eligible (1) |
| Eligible record | ASA **113005** present; Human-approved remains **0** |
| Product filters (matchable default earlier) | Windows 153 · Veeam 4 · … · Cisco 12 (sums to 181) |
| Live API totals | `governed_records=911`, `analyzer_matchable=181`, `other_governed=730`, `cert_class_b=39`, `eligible=1`, `human_approved=0` |

## Evidence files

- `evidence/knowledge-catalog-eligible-kpi.png`
- `evidence/live-identity-evidence.json`
- `evidence/live-eligible-page.json`

## Explicit non-claims

- Product Acceptance: **not claimed**
- Full V2–V12 / full pytest: **not re-run**
- Human Certification: **NOT RUN**
- Slide PDF: exported via PowerPoint COM (239,369 bytes); visual layout/font spot-check was not part of this browser check and remains to be completed before print use.
- 911 / 181 / 730 are **catalog identities/surfaces** (181 ⊂ 911 by proven `catalog_id`); **never summed** as additive totals
- Class B **39** is a **classification metric**, not a catalog total
