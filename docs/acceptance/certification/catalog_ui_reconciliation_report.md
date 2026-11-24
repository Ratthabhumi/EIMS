# EIMS — Catalog UI Reconciliation Report

**Date:** 2026-11-22  
**Role:** Cursor (focused UI/API presentation reconciliation)  
**Scope:** Diagnostic Knowledge Catalog tab and its data flow only  
**DOCX:** not edited  
**Commit/push:** none  

---

## 1. Baseline

| Item | Value |
|---|---|
| Branch | `demo/2026-11-24` |
| HEAD | `3f2beea` |
| Staged | **0** |
| Dirty/untracked (pre-edit count method) | **338** lines of `git status --porcelain` (preserved; this task adds/edits only the files listed below) |
| Forbidden file | `EIMS_11-8-2026.md` not inspected |
| Operational DB | not used |
| Portal `:3001` | not stopped/restarted; Turbopack not launched in this task |

Locked certification figures (unchanged by this work):

| Gate / figure | Value |
|---|---|
| Engineering Acceptance | PASS (inherited) |
| Human Certification | NOT RUN |
| Production Readiness | PARTIAL |
| Governed inventory | **911** |
| Eligibility | **1 / 42 / 868** |
| Human-approved | **0** |

---

## 2. UI-to-API data flow

```
AnalyzerHistoryList (tab "catalog")
  → requestCatalogEntries()
  → GET /api/v1/history/catalog
  → history.get_operational_catalog()
  → operational_catalog.get_catalog()
  → OPERATIONAL_CATALOG = load_catalog(
        operational_event_catalog.json,
        diagnostic_knowledge_catalog.json
     )
  → response { classification, surface, count, entries[] }
  → UI: tab badge = entries.length
       subtitle = operational vs candidate split + disclaimers
       product filter = count by entry.source_family
```

| Layer | Path / symbol |
|---|---|
| UI tab / subtitle / filters | `clients/dashboard/src/components/AnalyzerHistoryList.tsx` |
| UI fetch | `requestCatalogEntries()` → `apiUrl("/api/v1/history/catalog")` |
| HTTP route | `backend/api/routers/analyzer/history.py` `get_operational_catalog` |
| Loader | `backend/domain/analyzer/services/operational_catalog.py` `load_catalog` / `get_catalog` |
| Source JSON | `operational_event_catalog.json` + `diagnostic_knowledge_catalog.json` |

**Not on this tab:**

| Surface | Loader / API | Count (current tree) |
|---|---|---|
| Governed full inventory | `knowledge.service._catalog()` = `load_catalog()` + `DIAGNOSTIC_CANDIDATES` + `REFERENCE_CATALOG` | **911** |
| Eligibility | `catalog_import_eligibility.json` / adapter | **1 / 42 / 868** |
| Gate H “summary” probe (20 Nov) | `GET /api/v1/analyzer/catalog/summary` → `knowledge.service.summary` → `resolve_catalog()` | Same **parser-linked** set as `load_catalog()` (today **181**); Gate H recorded **175** as a dated snapshot |

Important: `resolve_catalog()` (summary API) loads **only** `load_catalog()`, not the full `_catalog()` 911 set. So summary and history/catalog share the same parser-linked surface; they do **not** expose 911.

---

## 3. Exact meaning and source of **181**

| Part | Count | Source | `knowledge_class` / lifecycle |
|---|---:|---|---|
| Windows operational context | **153** | `operational_event_catalog.json` | `operational_context` / `operational_context` |
| Vendor diagnostic candidates | **28** | `diagnostic_knowledge_catalog.json` `entries` | `diagnostic_candidate` / `candidate` |
| **Total (UI)** | **181** | sum of the two files via `load_catalog()` | — |

Product filter counts observed from the same loader (matches screenshot):

| `source_family` | Label | Count |
|---|---|---:|
| `windows_event` | Microsoft Windows | 153 |
| `veeam_vbr` | Veeam | 4 |
| `vmware` | VMware | 2 |
| `fortinet` | Fortinet | 5 |
| `cisco_asa` | Cisco ASA / FTD | 12 |
| `palo_alto` | Palo Alto PAN-OS | 4 |
| `linux_syslog` | Linux / OpenSSH | 1 |
| `json` | Structured JSON (parser only) | **0** (family exists for parsing; no catalog rows) |

**Includes:** only parser-linked / Analyzer-browsable records from the two JSON files above.  
**Excludes:** unmapped diagnostic candidates, vendor reference-only inventory, and other governed records that make the inventory **911**.  
**Does not mean:** validated solutions, root-cause confirmation, human approval, or eligibility=ELIGIBLE.

Disclaimers already present before this task (retained):

- Subtitle: Not validated solutions · Context ≠ root cause  
- Per-row: `Diagnostic candidate — not approved` / documented or legacy labels via `catalogTrustLabel`  
- Detail open path: “reference context… does not by itself confirm a root cause”

---

## 4. Reconciliation with **175** and **911**

| Figure | What it is | Relation to UI 181 |
|---|---|---|
| **175** | Same parser-linked surface **before** +6 Cisco ASA candidates (153 operational + 22 candidates). Gate H (20 Nov) measured `/api/v1/analyzer/catalog/summary` → `total_records=175`, `approved=0`, and the UI subtitle pattern. Documented in `2026-11-20-final-browser-e2e-acceptance.md` and knowledge-foundation expansion (175→181). | **Same surface, earlier snapshot.** Not a different API product. Do not “fix” UI back to 175. |
| **181** | Current `load_catalog()` total (153+28). What the Diagnostic Knowledge Catalog tab displays today. | **Correct count for this tab.** |
| **911** | Full governed working-tree inventory (`_catalog()` / register / eligibility). | **Different surface.** Must not replace the tab badge. Eligibility **1/42/868/0** applies to governed inventory, not as a re-label of 181. |

```
175  --(+6 ASA candidates)-->  181  ⊆  911
     same parser-linked loader      full governed inventory
```

---

## 5. Findings and severity

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| F1 | Count **181** matches loader math and product filters; not a stale/wrong total | Info | **No count change** |
| F2 | Tab/subtitle did not name the **parser-linked Analyzer** surface, so readers could equate 181 with governed **911** or freeze Gate H **175** as “the” catalog | Medium (misleading scope) | **Fixed** (subtitle wording) |
| F3 | Wording “operational/reference” could be confused with technical **reference-only** inventory (658) | Low | **Fixed** → “operational context” |
| F4 | API response lacked an explicit `surface` field (only `OPERATIONAL_EVENT_CATALOG`) | Low | **Fixed** → `surface: parser_linked_analyzer_catalog` |
| F5 | Gate H used summary API (175) while UI lists history/catalog; both are the same loader family | Info | Document only; no merge of endpoints required |
| F6 | `Structured JSON (parser only) (0)` is empty by design | Info | **Kept**; not a defect |
| F7 | Disclaimers “Not validated solutions · Context ≠ root cause” are accurate | Info | **Kept** |
| F8 | No evidence that UI promotes candidates to approved or shows synthetic human approval | — | No change |
| F9 | Open Access / no login | — | Untouched |

**Not done (out of scope):** replacing 181 with 175 or 911; governance policy; eligibility UI; DOCX edit; full regression; stopping `:3001`.

---

## 6. Files changed

| File | Change |
|---|---|
| `clients/dashboard/src/components/AnalyzerHistoryList.tsx` | Subtitle identifies parser-linked Analyzer catalog; “operational context”; states not full governed inventory |
| `backend/api/routers/analyzer/history.py` | Add `surface: "parser_linked_analyzer_catalog"` on `GET /api/v1/history/catalog` |
| `tests/test_diagnostic_catalog.py` | Assert `surface` and full `count == X.TOTAL` |
| `docs/acceptance/certification/catalog_ui_reconciliation_report.md` | This report |

No governance, eligibility, login, or unrelated UI/backend edits.

---

## 7. Focused test evidence

Command (project venv):

```text
.\venv\Scripts\python.exe -m pytest ^
  tests/test_diagnostic_catalog.py::test_catalog_api_filters_and_history_totals ^
  tests/test_diagnostic_catalog.py::test_exact_windows_preservation_and_counts ^
  -q --tb=short
```

Result: recorded in the shell transcript for this task (see §7.1 after run completes). Full suite **not** re-run.

Hermetic loader check (read-only Python during investigation):

```text
windows 153 + vendor 28 = 181
resolve_catalog (summary surface) = 181
_catalog (governed) = 911
vendor by_family = veeam 4, vmware 2, fortinet 5, cisco_asa 12, palo_alto 4, linux_syslog 1
```

Browser visual re-check against live `:3001` was **not** performed in this task (dev server left alone; no Turbopack). After Portal hot-reload or next manual refresh, subtitle text should match §6.

### 7.1 Pytest result

```text
..\venv\Scripts\python.exe -m pytest
  tests/test_diagnostic_catalog.py::test_catalog_api_filters_and_history_totals
  tests/test_diagnostic_catalog.py::test_exact_windows_preservation_and_counts
  -q --tb=short

..                                                                       [100%]
exit_code: 0
elapsed_ms: ~44073
```

**2 passed**, 0 failed. Full regression not run.

---

## 8. Remaining limitations

1. Live Portal on `:3001` was not restarted; operator must refresh to see subtitle copy if HMR did not pick up the TSX change.  
2. Tab title string remains “Diagnostic Knowledge Catalog (N)” for IA stability; scope clarity is in the subtitle + API `surface`.  
3. Governed **911** / eligibility **1/42/868** are still **not** rendered on this tab (by design).  
4. Secure Browser / certification browser layers unchanged.  
5. `final_report_correction_plan.md` should later note: **175 = dated Gate H snapshot of this same surface; 181 = current UI/API parser-linked total; 911 = separate governed inventory.**  
6. Human Certification remains **NOT RUN**; 0 human-approved.

---

## 9. Implications for Correction Plan / DOCX (no DOCX edit now)

| Report figure | Recommended research wording after this reconciliation |
|---|---|
| 175 | Gate H / early expansion snapshot of the **parser-linked Analyzer catalog** |
| 181 | **Current** Diagnostic Knowledge Catalog tab / `GET /api/v1/history/catalog` |
| 911 | Governed inventory / eligibility register — **not** the tab badge |

Do **not** rewrite Abstract 175 → 181 or 911 without an explicit dated dual-cite. Prefer: keep 175 as Gate H evidence; state 181 as current UI surface; keep 911 as governed inventory.

---

## 10. Stop

Investigation complete. Presentation defects F2–F4 fixed. Count 181 retained. DOCX not edited. No stage/commit/push.
)
