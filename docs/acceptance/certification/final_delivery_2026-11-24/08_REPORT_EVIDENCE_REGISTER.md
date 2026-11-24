# EIMS Report Evidence Register

**Prepared:** 2026-11-22 (Cursor, repository-direct)  
**Branch / HEAD:** `demo/2026-11-24` · `3f2beeafa3f28a98d9ff9f3ecf89b34978de07de` (`3f2beea`)  
**Working tree:** dirty preserved · **0 staged** · **no commit/push**  
**DOCX (historical draft):** `...\EIMS_FINAL_SUBMISSION_2026_FINAL_REVIEW_with_dotted_leaders.docx` — **do not copy numbers from DOCX without matching a claim below**  
**Canva:** `https://www.canva.com/design/DAHYXQN-j8k/lg-rK6VVoNG4ErShtP-uQA/edit` — MCP auth **rejected by user this session**; presenter notes plan in `09_CANVA_CHANGE_PLAN.md` (manual apply)

---

## A. Executive Summary (safe narrative)

EIMS is an Open Access engineering investigation platform for infrastructure evidence: collect → analyze → consult governed knowledge → investigate → remediate with risk awareness → verify with post-change evidence → close with audit trail.

**Verified for presentation (recomputed 2026-11-22 against HEAD working tree + live API `:8031`):**

| Capability | Status |
|---|---|
| Unified Knowledge Catalog contract (911 / 181 / 730) | **Verified current** |
| Analyzer-matchable product families sum to 181 | **Verified current** |
| UI labels distinguish inventory vs Analyzer products | **Verified current** (source + prior browser evidence) |
| Focused unified-catalog tests | **4 passed** (this session) |
| Engineering Acceptance | **PASS (inherited)** — not re-run full suite this session |
| Human Certification | **NOT RUN** |
| Production Readiness | **PARTIAL** |
| Product Acceptance | **NOT CLAIMED** |

---

## B. Engineering Work Completed (current, not DOCX-era)

1. Unified Catalog projection + API (`GET /api/v1/knowledge/catalog`, identity-evidence)  
2. Portal Knowledge Catalog KPIs + facets + **All Analyzer products (181)** labeling  
3. Machine-verifiable identity + knowledge-quality audit tooling  
4. Delivery package under `final_delivery_2026-11-24/`  
5. Prior engineering gates documented in certification handover (inherited)

---

## C. Evidence Register

### Catalog identity & counts

| Claim ID | Report claim | Evidence | Location | Verification | Result | Scope | Date/version |
|---|---|---|---|---|---|---|---|
| C-911 | Governed inventory has **911** records | `_catalog()` / register / live API totals | `backend/domain/knowledge/service.py` `_catalog`; `GET /api/v1/knowledge/catalog` totals.governed_records | Recompute identity_evidence + live curl | **911** | Full governed inventory | 2026-11-22 @ `3f2beea` WT |
| C-181 | Analyzer-matchable / parser-linked Analyzer surface has **181** records | `load_catalog()` | `operational_catalog.py`; totals.analyzer_matchable | Recompute + live API | **181** | Distinct **surface**; **exact subset** of 911 by `catalog_id` | same |
| C-730 | Other governed inventory = **730** | set difference 911−181 | identity_evidence.other_governed_count | Recompute | **730** | Outside Analyzer loader | same |
| C-175 | **175** is historical Gate H snapshot of Analyzer surface | Nov 20 E2E + expansion docs | `docs/acceptance/2026-11-20-final-browser-e2e-acceptance.md`; knowledge-foundation expansion | Document review | Historical only | **Not** a current catalog source | 2026-11-20 |
| C-SUB | 181 ⊆ 911 by exact `catalog_id` | identity_evidence.strict_subset | `unified_catalog.identity_evidence()` | Recompute True | Proven | Does **not** mean “same UX role” | 2026-11-22 |
| C-FAM | All Analyzer products family counts sum to **181** | by_analyzer_source_family | API totals; Windows 153+…+linux 1; json **0** | Live API fam_sum=181 | PASS | Product dropdown population | 2026-11-22 |
| C-B39 | Class B = **39** (=28 matchable + 11 not in load_catalog) | classify + identity | identity_evidence cert_class_b_* | Recompute 28+11=39 | PASS | **Classification metric**, not catalog total | 2026-11-22 |
| C-EL1 | Eligible = **1** (ASA 113005) | eligibility join | totals.eligible; eligibility JSON | Live + recompute | **1** | Import eligibility ≠ approval | 2026-11-22 |
| C-HA0 | Human-approved = **0** | certification / readiness | totals.human_approved; handover | Live + handover | **0** | Synthetic approvals excluded | 2026-11-22 |

### Knowledge quality

| Claim ID | Report claim | Evidence | Location | Verification | Result | Scope | Date/version |
|---|---|---|---|---|---|---|---|
| K-77 | **77/911** partial engineer-ready (what+inspect+action stated) | operational_view audit | `tools/audit_knowledge_quality.py`; `evidence/knowledge_quality_audit.json` | Re-run tool exit 0 | **77/911** | Field completeness, not approval | 2026-11-22 |
| K-19 | **19/911** full verify chain | same | same | Re-run | **19/911** | Includes risk+recoveryVerification | 2026-11-22 |
| K-ASA | ASA 113005 has stated investigation sections in operational_view; still not human-approved | audit asa block + eligibility | same + handover | Re-run | Stated fields true; HA=0 | Eligible for review only | 2026-11-22 |

### Testing & gates

| Claim ID | Report claim | Evidence | Location | Verification | Result | Scope | Date/version |
|---|---|---|---|---|---|---|---|
| T-4 | Focused unified catalog tests **4 passed** | pytest | `tests/test_unified_catalog.py` | This session exit 0 | **4 passed** | Contract/identity/family only | 2026-11-22 |
| T-LABEL | UI forbids “All products” ambiguous label | script | `scripts/check-catalog-ui-labels.mjs` | This session | OK | Source-level | 2026-11-22 |
| T-ENG | Engineering Acceptance **PASS** | handover/final_acceptance | `final_handover_report.md` | Documented inherited; **full suite not re-run this session** | **PASS (inherited)** | Do not present as same-day retest | 2026-11-22 docs |
| T-HUM | Human Certification **NOT RUN** | handover + HA=0 | same | Live HA=0 | NOT RUN | No human page review | current |
| T-PROD | Production Readiness **PARTIAL** | handover checklist | same | Document review | PARTIAL | Deployed controls mostly NOT VERIFIED | current |
| T-PA | Product Acceptance | — | — | Not completed | **NOT CLAIMED** | — | — |
| T-BR-CAT | Catalog UI browser check | prior closure screenshots | `evidence/knowledge-catalog-*.png`; `05_`, `06_` | Prior PASS; not re-clicked this session after DOCX prompt | **PASS (prior same-day evidence)** | Catalog tab only, not full A–H | 2026-11-22 earlier |
| T-2107 | Backend 2107/51/0 | end_to_end_final_report | certification | Historical finished-code | Historical | Not re-run this session | earlier cert |
| T-18 | Browser 18/18 | browser_acceptance_report | certification | Historical | Historical | Not re-run this session | earlier cert |

### Investigation semantics (code-backed)

| Claim ID | Report claim | Evidence | Location | Verification | Result | Scope |
|---|---|---|---|---|---|---|
| I-HYP | Hypothesis ≠ confirmed root cause | Incident Workspace copy | `IncidentWorkspace.tsx` | Code inspection | Present | UI honesty |
| I-FIX | Fix applied ≠ Resolved | same | same | Code inspection | Present | Verification/reviewer required |
| I-MATCH | Analyzer matches only Analyzer-matchable surface | load_catalog / entry_for_metadata | `operational_catalog.py` | Architecture | 181 only | Not 911 |

---

## D. Architecture (current)

```
Evidence → Analyzer API → PostgreSQL history/incidents
                ↓
     load_catalog (181) ←── Analyzer match path
                ↓
     _catalog (911) ←── Unified Catalog API / governance
                ↓
     Portal Knowledge Catalog (KPIs + Analyzer product filter)
```

Open Access reads; human-only governance writes.

---

## E. Testing and Quality (this session)

```
pytest tests/test_unified_catalog.py  → 4 passed (exit 0)
node scripts/check-catalog-ui-labels.mjs → OK
identity_evidence / live API → 911/181/730/39/1/0
audit_knowledge_quality.py → 77/911, 19/911
```

Full regression / full browser A–H / production probes: **NOT RUN** this session.

---

## F. Engineering Impact (supported)

EIMS improves: evidence retention, catalog-scoped Analyzer matching, honest hypothesis/fix/verify language, and a single catalog inventory with explicit Analyzer vs governance dimensions.

Unsupported: claiming all 911 rows are investigation-complete or production-certified.

---

## G. Future Development Roadmap

1. **Human Review workflow** for ASA 113005 + Cisco pages (acceptance: human-approved > 0 via real reviewers)  
2. **Verification/rollback quality** on high-impact Analyzer-matchable Class B (acceptance: increase K-19 without inventing sources)  
3. **Broader Product Acceptance** browser journeys after Catalog closure (acceptance: dated A–H re-run)  
4. **Production readiness controls** (secrets/TLS/backup/alerting verified in target env)  
5. **Operational monitors** (Relay / Persistent Monitor / Trust Grant) re-verified with current HEAD when next touched  

---

## Root-cause remediations this session

| Issue | Cause | Fix | Test |
|---|---|---|---|
| `audit_knowledge_quality.py` failed when run as script | Missing repo root on `sys.path` | Bootstrap `sys.path` | Tool re-run exit 0, wrote JSON |

No catalog identity/data changes. No UI/API count changes.

---

## Presentation deliverables status

| Deliverable | Status |
|---|---|
| `01_EIMS_Presentation.pptx` | Exists; claims align with register above — refresh speaker notes if rebuilt |
| `02_EIMS_Presentation.pdf` | **Exported** via PowerPoint COM (239,369 bytes) — open once on print PC to confirm fonts/layout |
| Canva presenter notes | **NOT APPLIED** (MCP auth rejected); see `09_CANVA_CHANGE_PLAN.md` |
| DOCX research report | **Not edited** this session; use Evidence Register before any DOCX rewrite |
