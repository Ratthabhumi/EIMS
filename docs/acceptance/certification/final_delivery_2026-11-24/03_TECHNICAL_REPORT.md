# EIMS Technical Report — Final Delivery Package

**Audience:** Technical reviewers · **Date:** 2026-11-22 · **Present:** 24 Nov 2026  
**Repository:** `demo/2026-11-24` @ `3f2beea` · staged 0 · dirty tree preserved  

Print this Markdown (or Word/PDF export) as `03 — EIMS Technical Report`.

---

## 1. Executive overview

EIMS supports infrastructure evidence collection, deterministic Analyzer investigation, incident workspace workflows, and a governed knowledge inventory. This delivery pass closes the **Unified Knowledge Catalog** contract so UI/API/KPI language match repository identity.

## 2. Architecture

Collector / EVTX-JSON → Backend API + PostgreSQL → Analyzer (parsers + catalog match) → Incident Workspace → Unified Knowledge Catalog projection → optional human governance.

Open Access reads; human-only verify/validate/approve.

## 3. Unified Catalog

| Dimension | Source of truth |
|---|---|
| Governed 911 | `_catalog()` |
| Analyzer-matchable 181 | `load_catalog()` exact subset |
| Other 730 | set difference |
| Class A–F | `catalog_adapter.classify` |
| Eligibility 1/42/868 | `catalog_import_eligibility.json` join |
| Human-approved 0 | register readiness / certification policy |

API: `GET /api/v1/knowledge/catalog` (+ `identity-evidence`).

## 4. Analyzer vs certification

Independent dimensions. Class B = 39 = 28 matchable + 11 cert-only. Analyzer must not claim all 911 or all 39.

## 5. Data lineage

Four JSON catalogs → projection → API totals → Portal KPIs. No hardcoded KPI in UI.

## 6. Security / integrity

Open Access identity `demo` for reads. Governance writes require reviewer capability. Synthetic disposable approvals excluded from certification human counts.

## 7. Test evidence

See `02_TEST_EVIDENCE.md` — 5 focused tests PASS (exit 0). Full suite not re-run.

## 8. Operational readiness

| Gate | Status |
|---|---|
| Engineering Acceptance | PASS (inherited) |
| Human Certification | NOT RUN |
| Production Readiness | PARTIAL |

Persistent Monitor / Result Relay / Trust Grant: not re-verified this pass (unchanged code paths).

## 9. Limitations

Diagnostic accuracy NOT MEASURED; RAG M2/M3 NOT RUN; Catalog-tab browser verification is recorded in `05_BROWSER_VERIFICATION.md` (full product A–H not re-run); slide PDF was exported, but visual layout/font spot-check remains outstanding.

## 10. Roadmap

Human review packages → Production controls → Optional RAG after gold dataset → Product Acceptance only after browser+human gates close.
