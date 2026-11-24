# EIMS — Unified Knowledge Catalog Architecture Assessment

**Phase:** 1 — Data Model and Identity Reconciliation (**READ ONLY**)  
**Date:** 2026-11-22  
**Branch / HEAD:** `demo/2026-11-24` · `3f2beea`  
**Staged:** 0 · dirty/untracked preserved · no commit/push  
**DOCX / schema / API / UI:** not modified in this phase  

Companion evidence: `catalog_ui_reconciliation_report.md` (181 surface clarified; focused tests 2 passed).

---

## 1. Verdict

| Question | Answer |
|---|---|
| Unify **user experience** into one Knowledge Catalog? | **Yes — feasible**, with an explicit projection layer |
| Treat 181 and 911 as one additive total? | **No** — 181 ⊂ 911; never sum |
| Implement now? | **Needs prerequisite work** before schema/API/UI (see §9) |
| Feasible without identity invention? | **Yes** for the 181↔911 join (exact `catalog_id` subset proven) |

**Recommendation:** `needs prerequisite work` → then Phase 2 Unified Catalog API.

Do **not** start UI rewrite until the projection contract and the two “parser” meanings below are named in API fields.

---

## 2. Exact source → API → UI data flow (current)

```
JSON sources
├── operational_event_catalog.json          (153 Windows)
├── diagnostic_knowledge_catalog.json       (28 vendor candidates)
├── vendor_diagnostic_catalog.json          (72 candidates; runtime key candidate:*)
└── vendor_reference_catalog.json           (658 references; runtime key reference:*)

load_catalog(ops + diagnostic_knowledge) ──► OPERATIONAL_CATALOG (181)
        │
        ├─► GET /api/v1/history/catalog     ──► AnalyzerHistoryList "Diagnostic Knowledge Catalog"
        │         surface=parser_linked_analyzer_catalog (added in prior UI pass)
        │
        └─► resolve_catalog()               ──► GET /api/v1/analyzer/catalog/summary
                  (also 181 only; governance overlay counts)

_catalog() = load_catalog() + DIAGNOSTIC_CANDIDATES + REFERENCE_CATALOG  ──► 911
        │
        ├─► knowledge governance / proposals (keyed by runtime catalog_id)
        ├─► register.json / eligibility.json (certification artifacts)
        └─► NOT listed by the current Catalog tab
```

| Surface | Count | Identity | Consumer today |
|---|---:|---|---|
| Parser-linked **Analyzer** catalog | **181** | `family:code_type:code` (e.g. `windows_event:official_event_id:1026`) | History Catalog tab; Analyzer `entry_for_metadata` |
| Summary API | **181** | same as above | Gate H historically reported **175** (pre–+6 ASA) |
| Governed inventory `_catalog()` | **911** | 181 keys + `candidate:*` (72) + `reference:*` (658) | Governance / cert tools |
| Eligibility artifact | **911** | `record_key` + `catalog_id` | Certification counts 1/42/868 |
| Register artifact | **911** | `record_key` (prefixed) | Class A–F |

Incident Workspace and Analysis History remain **separate workflows** (correct); they should **consume** the unified catalog, not host a second inventory.

---

## 3. Identity reconciliation results

### 3.1 Overlap (computed this phase)

| Check | Result |
|---|---|
| `len(load_catalog())` | **181** |
| `len(_catalog())` | **911** |
| Exact `catalog_id` overlap | **181** |
| Only in linked, not in governed | **0** |
| Only in governed, not in linked | **730** |
| `911 − 181` | **730** |
| **181 strict subset of 911?** | **Yes** (`linked_ids ⊆ gov_ids`) |
| Content-hash collisions inside `_catalog()` | **0** (911 unique hashes) |

So the mock KPI “Other governed records = 730” is **identity-proven**, not assumed.

### 3.2 Kind breakdown inside `_catalog()`

| `catalog_kind` | Count | In Analyzer tab (181)? |
|---|---:|---|
| `windows` | 153 | Yes |
| `legacy` | 28 | Yes |
| `candidate` | 72 | No |
| `reference` | 658 | No |
| **Total** | **911** | **181** |

### 3.3 Dual key schemes (compatibility risk)

| Artifact | Key form | Example |
|---|---|---|
| Runtime `_catalog()` / governance | bare for windows/legacy; prefixed for candidate/reference | `cisco_asa:official_message_id:113005` · `candidate:postgresql:locks:deadlock-detected` |
| Register / eligibility `record_key` | always catalog-prefixed | `diagnostic_legacy:cisco_asa:…` · `operational:windows_event:…` · `candidate:…` · `reference:…` |
| Register / eligibility `catalog_id` | often unprefixed for legacy/windows | Matches linked IDs for all **181** |

**Join rule that works today:**

- Linked ↔ governed: **exact runtime `catalog_id`**
- Linked ↔ eligibility/register: **`catalog_id` equality** (all 181 matched; 0 missing)

### 3.4 Linked subset eligibility (certification artifact)

| Status | Among 181 | Notes |
|---|---:|---|
| INELIGIBLE | 153 | All Windows class A |
| BLOCKED | 27 | Legacy candidates lacking import readiness |
| ELIGIBLE | 1 | `cisco_asa:official_message_id:113005` |
| Missing join | 0 | — |

Aligned with global **1 ELIGIBLE**; the other 730 contribute the remaining BLOCKED/INELIGIBLE mass.

### 3.5 Critical distinction: two “parser-linked” meanings

| Meaning | Count | Definition |
|---|---:|---|
| **A. Analyzer-matchable** | **181** | Present in `OPERATIONAL_CATALOG` / `GET /api/v1/history/catalog`; Analyzer can resolve via parsers + `entry_for_metadata` |
| **B. Certification class B** | **39** | Adapter `parser_linked_*` **or** legacy diagnostic file: **28** in Analyzer catalog + **11** only in `vendor_diagnostic_catalog.json` |

The **11** class-B-not-in-181 records (Fortinet×2, PostgreSQL×9) carry `parser_linked_by_*` in certification metadata but are **not** Analyzer-matchable through `load_catalog()`. A unified UI **must not** label them “available to Analyzer” solely because class = B.

Additionally, class **C** = **312** `parser_mapped` technical references: mapped for inventory/coverage, **not** Analyzer diagnostic match via the 181 loader.

---

## 4. Can non–parser-linked records appear safely?

**Yes**, if and only if the UI/API expose an explicit **`analyzer_availability`** (or equivalent) distinct from inventory membership:

| Record group | Show in unified list? | Analyzer investigation use |
|---|---|---|
| 181 Analyzer-matchable | Yes | May match when parser + identity resolve |
| 11 cert “parser_linked” outside 181 | Yes | **Not** via current Analyzer catalog path — show as inventory / future integration |
| Other candidates (E/D) | Yes | Not matchable; diagnostic intent only |
| References C/F | Yes | Definition / coverage only — never “validated solution” |

Required UX rule: **list ≠ analyze**. Default filters should make Analyzer-available records easy to find without hiding the rest of the inventory.

---

## 5. Proposed canonical data model (projection)

Do **not** merge JSON files or invent duplicate rows. Keep four source files; build a **read-only unified projection** keyed by runtime `catalog_id` (the `_catalog()` key).

### 5.1 Dimensions (API fields)

| Field | Type / enum | Source |
|---|---|---|
| `catalog_id` | string (stable runtime key) | `_catalog()` key |
| `record_key` | string (cert/register key) | register join |
| `inventory_scope` | `governed` (all 911 today) | membership in `_catalog()` |
| `source_catalog` | `operational` \| `diagnostic_legacy` \| `candidate` \| `reference` | register / loader |
| `knowledge_type` | `operational_context` \| `diagnostic_candidate` \| `technical_reference` \| `state_telemetry` | class / knowledge_class |
| `cert_class` | `A`–`F` | adapter/register |
| `parser_linkage` | `analyzer_matchable` \| `cert_parser_linked_only` \| `parser_mapped_reference` \| `not_linked` | **derived** (see rules) |
| `analyzer_availability` | `matchable` \| `not_matchable` | `catalog_id ∈ load_catalog()` |
| `eligibility` | `ELIGIBLE` \| `BLOCKED` \| `INELIGIBLE` \| … | eligibility artifact or live `evaluate` |
| `source_verification` | lifecycle / readiness | overlay + register readiness |
| `human_approval` | `none` \| `approved` \| … | overlay; **0** today for cert counts |
| `product` / `vendor` | string | record fields |
| `version_scope` | string \| null | record / register |
| `source_references` | list[{title,url,scope}] | normalized from heterogeneous source fields |
| `title` / `summary` | string | projected display fields |
| `content_hash` | string | canonical hash |

### 5.2 `parser_linkage` derivation rules

1. If `catalog_id ∈ load_catalog()` → `analyzer_matchable` (and `analyzer_availability=matchable`)  
2. Else if cert class B / `parser_mapping` starts with `parser_linked_` → `cert_parser_linked_only`  
3. Else if reference with `parser_mapping=parser_mapped` → `parser_mapped_reference`  
4. Else → `not_linked`

### 5.3 Example: ASA 113005

| Dimension | Value |
|---|---|
| `catalog_id` | `cisco_asa:official_message_id:113005` |
| Inventory | governed + analyzer_matchable |
| Eligibility | **ELIGIBLE** |
| Human approval | **none** (Human Certification NOT RUN) |
| Verification | unverified / package prepared only |

One row; many facets — no second catalog copy.

---

## 6. Proposed API contract (not implemented)

```http
GET /api/v1/knowledge/catalog
  ?q=
  &parser_linkage=analyzer_matchable|cert_parser_linked_only|parser_mapped_reference|not_linked
  &analyzer_availability=matchable|not_matchable
  &eligibility=ELIGIBLE|BLOCKED|INELIGIBLE
  &cert_class=A|B|C|D|E|F
  &product=
  &human_approval=none|approved|…
  &limit=&offset=
```

**Response sketch:**

```json
{
  "surface": "unified_governed_catalog",
  "totals": {
    "governed_records": 911,
    "analyzer_matchable": 181,
    "other_governed": 730,
    "eligible": 1,
    "blocked": 42,
    "ineligible": 868,
    "human_approved": 0
  },
  "totals_note": "Totals are facet counts over one inventory; never sum analyzer_matchable with governed_records.",
  "count": 50,
  "offset": 0,
  "limit": 50,
  "records": [ { "catalog_id": "...", "parser_linkage": "analyzer_matchable", "...": "..." } ]
}
```

**Compatibility:**

| Existing endpoint | Fate |
|---|---|
| `GET /api/v1/history/catalog` | Keep as **Analyzer-matchable subset** (or thin proxy `?analyzer_availability=matchable`) until Portal migrates |
| `GET /api/v1/analyzer/catalog/summary` | Keep; optionally add the same `totals` block |
| Governance proposal APIs | Unchanged keys (`catalog_id`) |

Open Access reads preserved; human-only writes unchanged. **No login requirement.**

---

## 7. Proposed UI architecture

**One** Knowledge Catalog page (replace the current tab’s role as the *only* inventory lens):

- Header KPIs (computed, not hardcoded): Governed 911 · Analyzer-matchable 181 · Eligible 1 · Human-approved 0  
- Facets: All · Analyzer-matchable · Not matchable · Eligible · Blocked · Approved · Product  
- Row chips: knowledge type · parser linkage · eligibility · verification · approval · Analyzer availability  
- Detail drawer: same record contract Analyzer/Governance already use  

**Keep separate:** Analysis History, Incident Workspace (workflows, not inventories).

**Do not:** show two competing “catalog home” pages; do not imply 911 matchable diagnostics.

Subtitle-only fix from the prior pass remains correct for the **current** tab until this UI ships; it is a stopgap, not the end state.

---

## 8. Migration sequence

| Phase | Work | Exit criteria |
|---|---|---|
| **1** | This assessment | Identity subset proven; dual parser meanings named |
| **2** | Unified projection module + `GET …/knowledge/catalog` | Totals 911/181/730/1/42/868/0 from live join; filters reconcile to listed rows |
| **3** | Portal Knowledge Catalog page | One list; facets; no duplicate inventory pages |
| **4** | Analyzer integration | Match path still only `analyzer_availability=matchable`; never silent fallback to references |
| **5** | Governance integration | Eligibility / verification / approval chips from overlay + artifacts; synthetic approvals excluded |
| **6** | Acceptance | Count, filter, identity, permissions, stale overlay, Open Access reads |

No data migration of JSON content required for Phase 2 if projection is compute-on-read (acceptable at 911 scale).

---

## 9. Risks and backward compatibility

| Risk | Severity | Mitigation |
|---|---|---|
| Confusing cert “parser-linked” (39) with Analyzer-matchable (181) | High | Separate API fields; UI copy review |
| Schema heterogeneity (ops vs candidate vs reference fields) | High | Projection/normalization; display “not stated” honestly |
| Dual keys (`record_key` vs runtime id) | Medium | Document join; prefer runtime `catalog_id` in new API |
| Stale eligibility JSON vs live adapter | Medium | Prefer live `evaluate` for API; artifact for certification freeze |
| Breaking Portal that expects 181-only payload shape | Medium | Keep history/catalog; version new route |
| Hardcoded KPI cards | Medium | Always derive from response `totals` |
| Performance if naive full-scan + DB overlay per row | Low–Med | Cache projection; overlay batch |
| Premature UI before contract | High | Gate Phase 3 on Phase 2 contract tests |

---

## 10. Tests required before/during implementation

1. **Identity:** `load_catalog` ids ⊆ `_catalog` ids; `|gov|-|linked|==730`; no hash collisions  
2. **Totals:** API totals match live joins (911/181/730 + eligibility summary)  
3. **Filters:** each facet count equals length of filtered `records` (no hardcoded 181/911)  
4. **ASA 113005:** single row; eligible; analyzer_matchable; human_approved=none  
5. **11 cert-only parser_linked:** listed; `analyzer_availability=not_matchable`  
6. **Analyzer regression:** `entry_for_metadata` / history catalog still return only matchable set  
7. **Open Access:** catalog GET remains readable without login; writes still reviewer-gated  
8. **Synthetic approval exclusion:** human_approved cert count stays 0 when disposable DB has synthetic events  
9. **Portal contract:** old history/catalog schema still valid until deprecation flag  

Do **not** re-run full regression for this assessment (no code changed here).

---

## 11. Impact summary

| Area | Impact |
|---|---|
| Analyzer | Read path unchanged until Phase 4; must keep matchable allowlist = 181 loader |
| Governance | Gains a browse surface; decision APIs stay on `catalog_id` |
| Existing tests | `catalog_expectations`, diagnostic catalog, knowledge service remain; add projection tests |
| Certification narrative / DOCX | Later: describe 911 inventory, 181 Analyzer subset, 1 eligible — already directionally correct in correction plan |
| Prior subtitle fix | Remains valid stopgap |

---

## 12. Explicit recommendation

**`needs prerequisite work`**

Prerequisites before coding UI:

1. Spec the projection module (field map ops/legacy/candidate/reference → unified record).  
2. Encode the two parser meanings as separate fields.  
3. Decide eligibility source of truth for the live API (artifact vs `evaluate`).  
4. Add contract tests for 911/181/730 and ASA 113005.  
5. Only then implement Unified Catalog API → UI.

**Feasible now (identity):** 181 is a proven strict subset of 911; 730 other governed records; no duplicate content hashes.  
**Not feasible as a shortcut:** summing counts, renaming the tab to “911” without facets, or treating class B (39) as Analyzer-ready.

---

## 13. Stop

Assessment only. No schema migration, API change, UI change, data rewrite, count replacement, synthetic promotion, login, test re-run, stage/commit/push, or DOCX edit in this phase.
)
