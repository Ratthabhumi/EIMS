# EIMS Consolidated Audit — Knowledge Foundation, Analyzer and Web (2026-11-22)

Read-only audit. No Knowledge was added, no frontend number was changed, no migration or import was run, no database was accessed, nothing was staged, committed or pushed, and `EIMS_11-8-2026.md` was not opened. Figures below were recomputed from the repository on 2026-11-22 (not copied from the older report). The only file written is this one.

**Repository:** branch `demo/2026-11-24`, HEAD `3f2beea`; working tree 312 entries (90 modified, 222 untracked), nothing staged. The Docker stack and the dev servers were stopped at the owner's request earlier today, so **nothing here was verified against a running web page**; every web finding comes from reading code.

---

## 1. Bottom line

1. **Why the Knowledge Base page did not change (evidenced from code):** the `/knowledge` page does not read the JSON catalogs that Tranches 1–18 edited. It reads two PostgreSQL tables through `/api/v1/knowledge/` (approved, active `KnowledgeEntry` rows, filled only by the human proposal/review workflow) and `/api/v1/knowledge/sources` (`KnowledgeSourceCandidate` rows, filled only by a separate guarded import of a different file, `docs/knowledge-source-candidates/official-vendor-candidates.v1.json`, 20 candidates dated 2026-11-15). None of the Tranche 1–18 work feeds either table. The Foundation's own status note already said this ("Engineering Knowledge Base is a separate module").
2. **Where the Tranche 1–18 data does reach the user:** only inside the Analyzer, when a pasted or uploaded log line parses to a matching identity (`summary.py` → `catalog_diagnostics.py`), and, for the 181 legacy records, in the public catalogue list `GET /api/v1/history/catalog` used by the Analyzer history list.
3. **911 is not a capability count.** Only 181 + 312 + 11 records can ever be reached by a parsed log line; 4 more are state evaluators with no API or UI caller; the rest are reference-only or unwired candidates (section 4).
4. **Nothing is human-reviewed or approved:** 72 candidates and 54 Windows dispositions are PENDING_HUMAN_REVIEW; source_verified / validated / approved are 0 / 0 / 0.

---

## 2. What each tranche added (from the Knowledge expansion report, headings re-checked)

| Tranche | Added / changed |
|---|---|
| 1–2 | Official references for Windows records; Defender-list corrections |
| 3 | `vendor_reference_catalog.json` (Reference-only inventory, 658 records) and coverage tooling |
| 4 | Windows records without a reference — pass 1 |
| 5 | Breadth batch: messaging, web/HTTP, Linux errno, load balancer references |
| 6–10 | Four-vendor deep diagnostics (Microsoft, Cisco, Fortinet, Veeam) into `vendor_diagnostic_catalog.json`; FortiOS 6.2 debug and SSL VPN; Veeam restore/SOBR; ASA failover |
| 11 | Windows Defender 1122 / 5010 / 5011 and WMI-Activity |
| 12 | Parsers for PostgreSQL and systemd Reference records (312 become parser-mapped) |
| 13–16 | PostgreSQL diagnostic candidates linked by SQLSTATE and by documented messages; upstream-source confirmation |
| 17 | Cisco NX-OS, Fortinet HA/logging, Veeam snapshots, two more Windows references |
| 18 | 54-record Windows disposition file; Fortinet policyid=0 and HA candidates; PostgreSQL state/telemetry evaluators; loader types `parser_linked_by_fields`, `state_telemetry_evaluator`; Human Review Package |

Files (current): data — `operational_event_catalog.json`, `diagnostic_knowledge_catalog.json`, `vendor_reference_catalog.json`, `vendor_diagnostic_catalog.json`, `windows_reference_dispositions.json`; code — `vendor_reference.py`, `vendor_diagnostics.py`, `catalog_diagnostics.py`, `state_diagnostics.py`, `parser.py`; tools — `knowledge_coverage_report.py`, `build_human_review_package.py`; docs — the expansion report and `2026-11-20-human-review-package.md`. Relationship: parser → identity → `reference_for_metadata` (Reference catalog) → optional `candidate_for_*` (diagnostic candidates) → `catalog_summary` text. State evaluators stand alone.

### Status per tier (strictest label that the evidence supports)

| Tier | Implemented | Tested | Integrated in Analyzer | Human-reviewed | Approved |
|---|---|---|---|---|---|
| 153 Windows operational-context records (111 with an exact reference) | yes | yes | yes (catalog list, summary) | no | no |
| 28 legacy parser-linked candidates | yes | yes | yes | no | no |
| 312 parser-mapped references (PostgreSQL 261, systemd 51) | yes | yes | yes, definition only | no | no |
| 11 log-linked candidates (5 SQLSTATE, 4 message, 2 field) | yes | yes | yes, only for matching input | no | no |
| 4 state/metrics candidates | evaluators for 3 | yes (unit) | **no — no caller** | no | no |
| 346 reference-only records | data only | schema tests | no | no | no |
| 57 remaining log-symptom candidates (Veeam 28, Cisco 9, Fortinet 14, Microsoft 6) | data only | schema tests | **no** (`candidate_for_future_integration` / `missing_parser`) | no | no |

---

## 3. Why the web did not change — traced path

| Hop | Evidence | Result |
|---|---|---|
| JSON catalogs → loader | `operational_catalog.py:57,111` loads **only** `operational_event_catalog.json` + `diagnostic_knowledge_catalog.json` into `OPERATIONAL_CATALOG` (181) at import time | the 658 and 72 records are not in this list |
| Loader → DB | `domain/knowledge/service.py` reads `load_catalog()` for lifecycle/gating logic; no code writes catalog records into `KnowledgeEntry`; `KnowledgeSourceCandidate` is filled only by `tools/import_knowledge_source_candidates.py` (dry-run default; apply needs `EIMS_SOURCE_CATALOGUE_IMPORT_ALLOWED_DATABASES`) from the 20-record docs JSON | Tranche data never reaches Knowledge tables |
| DB → API | `knowledge.py:573` lists `status == approved` and `lifecycle_state == active`; `:667` lists source candidates | empty until a human approves, or until the guarded import is applied |
| Catalog → API | `history.py:77` `GET /api/v1/history/catalog` returns the 181; `catalog.py` `/summary`, `/record` | 658 / 72 have **no list or count endpoint** |
| API → frontend | `clients/dashboard/src/app/knowledge/page.tsx` fetches `/api/v1/knowledge/`, `/sources`, `/review-queue`, `/lifecycle/review-queue`; `AnalyzerHistoryList.tsx:1051` fetches `/api/v1/history/catalog` | the page shows DB rows, not the catalogs |
| Runtime refresh | the catalogs load at process import; `/history/catalog` sends `Cache-Control: public, max-age=300` | the Windows changes (111 references, corrected 4199 and Disk 51) appear in the history catalogue only after a backend restart and up to 5 minutes of cache |
| Migrations | `f3c8a1d6b902_add_knowledge_source_candidates.py` and other knowledge migrations are **untracked** files | whether they are applied to the DB the web uses is **unverified** (no DB access) |

What this means for the page: nothing was "broken". The work was never connected to that page, and the page by design shows only human-approved Knowledge and imported source candidates.

---

## 4. Analyzer capability, separated (recomputed)

| Group | Count | Reachable through the Analyzer? |
|---|---:|---|
| Parser-linked legacy diagnostic candidates | 28 | yes (ASA 12, Fortinet 5, Veeam 4, PAN 4, VMware 2, OpenSSH/linux 1) |
| Parser-mapped references (definitions) | 312 | yes, shown as vendor reference text; not diagnostic workflows |
| Parser-linked candidates outside legacy | 11 | yes, for matching jsonlog SQLSTATE, `postgres*` syslog messages, or Fortinet traffic fields (tests) |
| State/telemetry candidates | 4 (3 evaluator-mapped) | **no**: `grep` finds `evaluate_*` only in `state_diagnostics.py` and tests; no endpoint, no UI, no collector supplies a `pg_replication_slots` / `get sys ha status` row |
| Candidates with no parser or evaluator | 57 (49 `candidate_for_future_integration`, 8 `missing_parser`; the 4 state candidates are counted separately) | no |
| Reference-only (`missing_parser`) | 346 | no |
| Windows operational context | 153 | yes (catalog + summary) |

Distinct capability that a pasted log line can trigger today: 28 + 11 + the parser-mapped definitions (312) + Windows context (153). The 911 headline double-counts nothing, but it mixes tiers.

---

## 5. Quality and safety findings (recomputed by script)

- **IDs:** no duplicate `catalog_id` (181), reference id (658) or `candidate_id` (72); no cross-file collisions.
- **Sources:** 188 distinct URLs, all `https://`; every candidate has a version scope, limitations and at least one source.
- **Labels:** all 72 candidates are `candidate` / `candidate` / `PENDING_HUMAN_REVIEW`; no candidate evidence text claims approval or validation.
- **Finding A (needs a decision):** 22 of the 28 legacy diagnostic entries carry `verification_status = official_documentation_verified` (6 more `code_supported_with_contextual_reference`), and an existing test asserts it. The Foundation reports `source_verified = 0`. Either the field means something narrower than "source_verified" (then rename/document it) or it is an unreviewed promotion. I did not change it.
- **Finding B:** 22 of 72 candidates mention a state-changing verb (delete/drop/rebuild/restart…) in remediation; 4 of them state no operational risk beyond "Not stated … Inference" (`microsoft-windows-dhcp:client:cannot-obtain-lease`, `microsoft-hyper-v:management:console-connect-or-auth-failure`, `cisco-ios:bgp:session-reset-on-interface-flap`, `veeam-vbr:restore:entire-vm-post-restore-differences`). The text is honest about it; a reviewer should still confirm each.
- **Finding C (found and fixed during Tranche 18):** an earlier rewrite of Disk 51 dropped the legacy "do not replace hardware…" guard; a failing test caught it and it was restored. Two legacy meaning errors (TCP/IP 4199, Disk 51 severity) were corrected from Microsoft pages.
- **Human Review Package:** covers the 54 dispositions and all 72 candidates (126 blank reviewer tables). It does **not** cover the 28 legacy candidates, the 312 parser-mapped references, the 346 reference-only records, or the 111 Windows records that already had exact references. Those remain unreviewed and outside the package.
- **Version honesty:** Fortinet 6.2.x applicability rests on tags, not text; 6.2.14 is not claimed anywhere (checked in tests).

---

## 6. Test evidence (from logs, not memory)

| Run | Result | Source |
|---|---|---|
| `pytest tests --ignore=tests/test_analyzer_postgres_integration.py`, disposable non-superuser PostgreSQL | **1903 passed, 51 skipped, 0 failed** (389.78 s, exit 0) | `scratchpad/final8_main.txt` |
| `tests/test_analyzer_postgres_integration.py`, disposable DB | **75 passed, 0 failed** (45.30 s, exit 0) | `scratchpad/final8_apg.txt` |
| Same suite without PostgreSQL | 1746 passed, 208 skipped, 0 failed (counted from dots; pytest summary lost to a Windows temp-dir cleanup `PermissionError`) | `scratchpad/full2.log` |
| Knowledge expansion, parser mapping, state diagnostics, Windows dispositions, vendor candidates | included in the 1903 | — |
| Frontend build / typecheck / `tests/analyzer_catalog_ui.cjs` | **Not run** | — |
| Browser check of the Knowledge page and Analyzer | **Not run** (stack stopped) | — |
| Fortinet/PG state evaluators through the API | **Not applicable** (not wired) | — |

The 51 skipped are environment-gated and are not counted as passed. Nothing in the suite exercises "Tranche 18 data appears on a web page".

---

## 7. Remaining gaps

1. No path exists from the 658 reference / 72 candidate catalogs to any list, count or Knowledge page.
2. State/telemetry evaluators have no caller, no input collector and no UI.
3. 57 candidates have no parser or evaluator; 346 references have no parser.
4. Human review: zero reviewers; 28 legacy candidates and all references sit outside the package.
5. Finding A (verification label) and Finding B (risk text) unresolved.
6. Migrations untracked; DB state unknown; nothing committed.
7. M2/M3 (RAG / semantic retrieval) and Diagnostic Accuracy: not evidenced here; do not claim them.

---

## 8. Recommended plan

**Before the Knowledge Base can show the new data (needs an owner decision, section 9):**
1. Decide what the page is for. Option 1: keep it for human-approved Knowledge only (then add a separate, read-only "Reference catalogue" view). Option 2: surface catalog tiers on the existing page.
2. Add a read-only API that returns the four catalogs' counts and records, tier-labelled (`operational_context`, `parser_linked_candidate`, `state_candidate`, `reference_only`), computed from the loaded catalogs — no hard-coded numbers.
3. Frontend reads that API; shows each tier separately with "pending human review".
4. Restart the backend (catalogs load at import) and mind the 5-minute catalogue cache.

**Before demonstrating the Analyzer:**
5. Run the existing synthetic lines end to end through the running stack (PostgreSQL jsonlog SQLSTATE, `postgres` syslog checkpoint message, Fortinet `policyid=0` local vs forward, a Windows 4199/51 event) and capture screenshots; not yet done.
6. Say plainly that state/telemetry candidates are documentation, not live diagnostics, unless a collector is built.

**Before the Foundation can be called verified:**
7. Independent human reviewers fill the package; only then may lifecycle move (never by an AI).
8. Extend the package to the 28 legacy candidates and the Windows records with references, or declare them out of scope.
9. Resolve Finding A and B.

**Later:** parsers/evaluators for the 57 unlinked candidates; a state collector; M2/M3; Diagnostic Accuracy evaluation.

---

## 9. Decisions needed from the owner (not guessed)

1. Should the Knowledge page show catalog tiers, or should a new read-only "Reference catalogue" page be created and the Knowledge page left for approved Knowledge?
2. Should I check the real database state (migrations applied, `KnowledgeSourceCandidate` row count)? I will not touch the operational DB without explicit permission; a disposable DB check is possible instead.
3. Is `official_documentation_verified` on 22 legacy entries acceptable wording, or must it be relabelled to avoid implying source verification?
4. May I start the stack and capture browser evidence of the Knowledge page and an Analyzer run (read-only)?

## 10. Notes for the thesis (no overclaiming)

- Do not write 911 as diagnostic capability. Safe wording: 153 Windows operational-context records, 28 + 11 parser-linked diagnostic candidates, 312 parser-mapped definitions, 4 state-based candidates (documentation only), 346 reference-only records, all unreviewed.
- Do not claim the Knowledge Foundation is complete, Diagnostic Accuracy has passed, or RAG/semantic retrieval works.
