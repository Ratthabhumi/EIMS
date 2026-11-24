# EIMS Knowledge Foundation Certification Program — Round 1 Proposal (2026-11-22)

**Scope of this round:** design only — framework, data model, review workflow, pilot plan, and structural problems found in the existing code. No code, data, schema, database or catalog was changed; nothing was staged, committed or pushed; `EIMS_11-8-2026.md` was not opened. Problems are reported here before anything is fixed, as requested. Figures come from the 2026-11-22 audit (`2026-11-22-consolidated-audit.md`) and were re-derived from the repository.

Principle: **a record is certified only by recorded evidence plus an independent human decision.** URLs, passing unit tests, or an AI reading a page are inputs to a human reviewer, never a certification. Target counts for "Approved" are outcomes, not goals; the program is successful when every record has an honest, evidenced status, including "rejected" and "blocked".

---

## 1. Problems found in the existing structure (report-first; nothing fixed)

| # | Problem | Evidence | Consequence for certification |
|---|---|---|---|
| P1 | The governance engine (lifecycle, gates, append-only events) covers only the 181 records returned by `load_catalog()` | `knowledge/service.py:17,69,79` builds its catalogue from `operational_catalog.load_catalog`; `vendor_reference_catalog.json` (658) and `vendor_diagnostic_catalog.json` (72) are loaded by other modules and have no `catalog_id` in that list | 730 of 911 records cannot be given a lifecycle status today |
| P2 | `operational_context` records can never leave `candidate` | `service.py:181` `if knowledge_class == OPERATIONAL and target != "candidate": reject`; `default_lifecycle` = `not_applicable` | The 153 Windows records have no certification path |
| P3 | One lifecycle for every class; gates are chosen by target state, not by record class | `gates.py` `evaluate_gate(... target ...)` | Reference-only and state/telemetry records would be held to the diagnostic-candidate gate (or not governable at all) |
| P4 | Reviewer identity is a free string; nothing says whether the actor is a human, an AI assistant or a script | `knowledge_review_event.actor String(255)`; gates compare actor strings only | An AI-written event could satisfy "independent approver" by using a different string |
| P5 | The "technical validation", "independent review", "blocked" notions the program needs are not states | `LIFECYCLE_STATES` = candidate, source_verified, validated, approved, rejected, deprecated, superseded | The dashboard cannot show Technically Validated / Independently Reviewed / Blocked separately without extra structure |
| P6 | Reviews are bound to a content hash; any catalog edit marks a record stale | `gates.py` compares `source_hash` to `content_hash`; `review_required` | Content must be frozen before a review batch, or reviews are silently invalidated |
| P7 | 22 of the 28 legacy diagnostic entries already carry `verification_status = official_documentation_verified` (a test asserts it) while the governance count of source_verified is 0 | audit Finding A | Two vocabularies for "verified"; must be reconciled before counts are shown |
| P8 | Several knowledge migrations are untracked files; whether they are applied to the DB the web uses is unknown | `git status` | Any DB-backed certification needs a confirmed schema; no DB was queried |
| P9 | No read API exposes catalog tiers or governance counts to the web | audit §3 | The dashboard needs a new read-only endpoint |
| P10 | State/telemetry candidates (4) have no caller, and their expected behaviour has only been checked against hand-written rows | audit §4 | Technical validation of these needs real PostgreSQL / FortiGate output, not synthetic dicts |

None of these was changed. P1, P2 and P4 are blocking for the program; P3 and P5 are design decisions (section 6).

---

## 2. Record classes and certification criteria

The 911 records fall into six classes (recomputed): Windows operational context 153 · parser-linked diagnostic candidates 28 legacy + 11 new = 39 · parser-mapped technical references 312 · state/telemetry 4 · unmapped diagnostic candidates 57 · reference-only 346. (153 + 39 + 312 + 4 + 57 + 346 = 911.)

Three evidence dimensions, recorded separately per record. A criterion that does not apply to a class is marked *N/A (by rule)*, never skipped silently.

| Class | S — Source verification (human) | T — Technical validation | D — Diagnostic validation (human) | Approval scope if all pass |
|---|---|---|---|---|
| **A. Windows operational context (153)** | Provider+Event ID on an official page; title/severity/meaning match; page read by a human | Catalog identity resolves via `resolve_windows_entry` for provider aliases; no ID collision across providers | *N/A* (context only, makes no diagnosis) — instead review that operator text makes no unsupported cause/remediation claim | `approved_as_context` |
| **B. Parser-linked diagnostic candidates (39)** | Each cited page read; claims quoted with section; version scope checked | Real sample lines → parser → identity → summary; negative fixtures (near-miss lines must not match); output text equals the intended claim | Symptom, causes, checks, remediation, warnings and rollback reviewed by a domain reviewer | `approved_as_diagnostic` |
| **C. Parser-mapped technical references (312)** | Code/name/meaning match the official table row | Mapping parser→code verified for every row by script; mis-parse fixtures | *N/A* (definition, not workflow) | `approved_as_reference` (explicitly "not a diagnostic") |
| **D. State/telemetry (4)** | As B | Evaluator run against **real output** from a disposable PostgreSQL (and real FortiGate-style CLI text where obtainable), not only synthetic dicts; thresholds none unless documented | As B, plus reviewer confirms "attention" semantics | `approved_as_state_reference` until a collector and caller exist; never labelled live diagnostic |
| **E. Unmapped diagnostic candidates (57)** | As B | Schema/limitations/sources tests only (no parser exists) | As B | `approved_as_reference` only; may not be called a diagnostic capability until a parser/evaluator is built and class B/D criteria are met |
| **F. Reference-only (346)** | Page/table row matches the record | Schema, URL reachability record, no parser required | *N/A* | `approved_as_reference` |

Approval scope is a new, explicit field so that "approved" can never be read as "the Analyzer can diagnose this".

Common rules (all classes): version scope stated and quoted; no universal meaning from a single scenario page (e.g. Fortinet `policyid=0`, SCM 7036); remediation carrying a destructive verb needs a stated risk and rollback or an explicit "not stated" accepted by the reviewer; every claim traceable to a source passage; content hash recorded.

---

## 3. Proposed data model (additive; not implemented)

### 3.1 Certification Register (generated artifact, read-only)
`tools/build_certification_register.py` (to be written after approval) emits `docs/acceptance/certification/register.json` (and a CSV view), one row per record, **derived** from the four catalogs and, when available, the governance tables. It stores no decisions itself.

| Field | Meaning |
|---|---|
| `record_key` | stable `<catalog>:<id>` (`operational:`, `diagnostic_legacy:`, `reference:`, `candidate:`) — also resolves P1 |
| `cert_class` | A–F above (derived by rule from `knowledge_class`, `parser_mapping`, `detection_kind`) |
| `content_hash` | SHA-256 of the canonical record (same function as `knowledge/service.py`) |
| `source_urls`, `quoted_claims`, `version_scope` | from the record; `quoted_claims` is empty until a reviewer fills it |
| `parser_or_evaluator` | mapping type and symbol |
| `test_evidence` | list of test node IDs and the log/run they passed in (generated; never typed) |
| `limitations`, `risks`, `destructive_verbs` | from the record + automated scan |
| `dimension_status` | `{S, T, D}` each one of `not_started / evidence_collected / passed / failed / not_applicable` with reason |
| `automation_findings` | output of automated checks (section 4) |
| `review` | `{reviewer_id, reviewer_kind, decision, decided_at, rationale}` — **empty until a human acts** |
| `status` | derived from governance state; one of the dashboard states below |

### 3.2 Governance DB (extends the existing tables; needs an owner-approved migration)
Reuse `knowledge_review` / `knowledge_review_event` (their `catalog_source` column already exists). Proposed additive changes:
1. Event column `actor_kind` ∈ {`human`, `ai_assist`, `automated`}; gates require `human` for `source_verified`, `validated`, `approved` (fixes P4). `ai_assist` and `automated` events may only record *evidence collected*, never a decision.
2. Event `evidence` JSONB gets a documented schema: `{dimension: S|T|D, artifacts: [...], automated: bool, quotes: [...]}` (P5) — dimensions are evidence tags on events, not new lifecycle states.
3. Review row gets `cert_class` and `approval_scope`; gates become class-profiles (P3) so classes A, C, F do not need D.
4. A class-A track so operational context can be approved as context (P2).
5. Loader extended so all 911 records have a `record_key` (P1).
Existing states, the append-only trigger, content-hash binding and the independence rule are kept.

### 3.3 Dashboard states (computed, never hard-coded, never merged)
`total` · `source_verified` · `technically_validated` · `independently_reviewed` (a different human than the verifier, with a decision) · `approved` (+ by scope) · `rejected` · `pending_review` · `blocked_insufficient_evidence` (flag with reason, e.g. no page found, needs real telemetry). Each shown as a number **and** a denominator for its class. A read-only endpoint `GET /api/v1/knowledge/certification/summary` computes them from the register and governance tables.

---

## 4. Automated validation (evidence for humans, not certification)

A single tool, `tools/validate_knowledge_certification.py`, run against fixtures and a disposable database only, producing `automation_findings`:
- duplicate / colliding IDs; cross-file consistency (counts must reconcile with the register);
- URL syntax, https, host allow-list per vendor; **reachability check recorded with date and hash of fetched text** (network-based, run only when allowed);
- version scope present and not broader than the quoted source (heuristic flags, human decides);
- parser matching with positive and **negative** fixtures per linked candidate; every `parser_mapped` reference resolves to a code that the parser can emit (and vice versa);
- evaluator tests against real disposable-PostgreSQL output for the state class;
- remediation scan: destructive verbs without stated risk/rollback, unqualified "always/never", causes asserted as certain;
- test-evidence completeness: each record in classes B/D has at least one positive and one negative test, discovered by node ID, not by count.
A failed automated finding blocks submission to review; a passed one never certifies.

---

## 5. Review workflow

```
Freeze batch (content hash recorded)  →  Evidence pack generated (sources, quotes, tests, findings)
  →  S: human source verification (reviewer 1)  →  T: automated + human-checked technical validation
  →  D: human diagnostic/safety review (domain reviewer, class B/D/E only)
  →  Independent approval (reviewer 2 ≠ reviewer 1/domain reviewer, ≠ contributor)  →  approved@scope
Any step may →  rejected (reason) | blocked (reason) | reopened (content changed ⇒ hash mismatch)
```
Rules: AI may collect evidence, compare documents, check consistency and propose a verdict; it may not write a decision event, supply a reviewer name, or approve. Records with no independent reviewer stay `pending_review`. Review packages are generated per batch (class × risk), not as one 911-item document, and extend the existing Human Review Package (which covers 126 of the 911 today) to all classes. Reviewer capacity is the real constraint: the program is paced by human review hours, not by tooling.

Batch order (risk and use): (1) B + D classes (39 + 4: Analyzer-live or state-live) → (2) A Windows with exact references (111) then the 42 without → (3) C parser-mapped references, split by product (PostgreSQL 261, systemd 51) → (4) E unmapped candidates (57) → (5) F reference-only (346).

Open owner decision on C (312, mostly a generated PostgreSQL SQLSTATE table): approve **per row**, or approve **table-level** (reviewer verifies the generator, a full automated diff against the official table, and a stated sample) and record the approval basis honestly as `table_level_review`. I recommend table-level with a mandatory full automated diff, but this is the owner's call.

---

## 6. Pilot plan (before scaling)

Goal: prove the workflow end to end on every class with the fewest records, on a **disposable** database, and measure review effort. Pilot ≈ 24 records:

| Class | Records |
|---|---|
| B | 1 ASA, 1 Fortinet legacy, 1 Veeam legacy |
| B (new) | PostgreSQL deadlock (SQLSTATE), PostgreSQL checkpoint message, Fortinet `policyid=0` local |
| D | PostgreSQL slot WAL retention, FortiGate HA selection |
| E | 1 Cisco, 1 Veeam |
| A | TCP/IP 4199, Disk 51, SCM 7036, one 'no reference found' record |
| C | 3 PostgreSQL SQLSTATE rows, 1 systemd row |
| F | 3 reference-only |

Pilot steps: (1) build the register for all 911 (read-only); (2) run the automated validator on the 24; (3) for class D, run the evaluators against a real disposable PostgreSQL replication pair; (4) generate the evidence packs; (5) exercise the workflow engine on a disposable DB with clearly labelled **TEST** actors, whose events are excluded from every count and are never described as reviews; (6) ask real humans to review as many of the 24 as available. Pilot success: every class has a working evidence pack and gate profile; the validator catches the known problems (e.g. missing negative tests, destructive verb without risk); the dashboard numbers are computed, with denominators; and the measured human minutes per record give a realistic estimate for the remaining 887.

Schedule honestly: pilot tooling ≈ 2–3 working days; human review of the pilot depends on reviewer availability and cannot be compressed by tooling.

---

## 7. What this proposal deliberately does not do
No status was changed; no record is marked reviewed; no migration or import was run; no operational DB was touched; no frontend number was hard-coded; nothing was committed.

## 8. Decisions needed from the owner (please answer before Round 2)
1. Approve the governance-DB changes in 3.2 (actor_kind, class profiles, approval scope, loader coverage of all 911)? They need a migration that I would test only on a disposable database.
2. Approach for the 312 parser-mapped references: per row or table-level (section 5)?
3. Who are the human reviewers (names stay yours to enter; I will not invent any), and how many hours per week are available? This sets the real timeline.
4. Reconcile `official_documentation_verified` (P7): relabel to an automated-check label, or have a human review those 22 first?
5. May I run read-only network URL reachability checks, and start a disposable PostgreSQL replication pair for class D evidence?
6. Should the first dashboard be a new read-only page, or added to the existing Knowledge page?
