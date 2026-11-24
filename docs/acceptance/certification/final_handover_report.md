# EIMS final handover report (2026-11-22)

Phase change: development is closed; the project moves to **certification and handover**. No code was changed in this pass. No login or sign-in was added (intentional product design). Nothing staged, committed or pushed. No synthetic event is, or may be treated as, human certification.

## Verdicts
| Gate | Verdict |
|---|---|
| Engineering Acceptance | **PASS** (as reported: 18/18 browser cases, 2107 passed / 51 skipped / 0 failed backend, analyzer-PG 75 passed, 23 focused governance/draft tests passed, `tsc` clean, webpack production build passed) |
| Human Certification | **NOT RUN** (0 human reviews or approvals; ASA 113005 and the five Cisco pages are unreviewed) |
| Production Readiness | **PARTIAL** (judged against the open-access design; deployment evidence below is mostly NOT VERIFIED) |

## Existing policies
* **Open access:** no application login; the Analyzer, operational guidance and the governance read views (queue, record, history) are open. **Writes** (draft save/submit/withdraw, every decision) require the reviewer capability: a database user with the reviewer flag (or admin) and a live session; the shared admin token, anonymous callers and non-reviewers are refused; the server sets the decider and its kind.
* **Governance gates** (`backend/domain/knowledge/gates.py`): verify, validate, approve, deprecate and supersede are human-only (`actor_kind == "human"`, fail closed); approval needs prior human verify and validate on the current revision, not stale; the approver must differ from the verifier and the validator; a contributor and the author of a submitted draft cannot approve their own work. **A three-reviewer rule is not an existing policy**; the mechanical minimum is two distinct humans. No gate change was made; a three-person rule would be a separate owner decision.

## Reviewer readiness
* Sourcing and qualification criteria, independence and conflict-of-interest declaration, evidence categories: `reviewer_sourcing_and_qualification_report.md`. Publicly verified qualifications: none; unverified candidate information: none; actual acceptance: none. No names, availability or contacts were produced; nobody was contacted.
* **ASA 113005:** package and worksheet ready (`asa_113005_review_package.md`), three roles (ASA/firewall, AAA/identity, network security operations). Authentication rejection and authorization rejection are separated. The original Cisco page has **not** been read by anyone; message statements come from a search summary and must be confirmed from the page.
* **Cisco five pages:** assignments and worksheet ready (`cisco_five_page_review_assignments.md`) by product domain: firewall HA (1), BGP (2), switching (1), NX-OS (1). All five returned HTTP 403 to automated retrieval, were not bypassed, and remain pending human reading.

## Data integrity (re-derived from `catalog_import_eligibility.json`)
911 records: 1 ELIGIBLE (`cisco_asa:official_message_id:113005`), 42 BLOCKED, 868 INELIGIBLE, **0 human-approved**. Class totals A 153, B 39, C 312, D 4, E 57, F 346. The 16-record research is complete for this scope (7 gained quotes, 9 had nothing further; 14 are class E without a parser and 2 class D without a collector; none became eligible) and is not repeated. Further research on the nine is justified only by a new official source or by a parser/collector that can use it. Synthetic test events (disposable DB `eims_analyzer_it`: `synthetic-browser-review`, `synthetic-stale-*` users, an approval by synthetic reviewers, and the older demo-seed approval by `demo.reviewer`) are append-only, left in place, labelled synthetic, and excluded from every certification count (counts come from repository artifacts).

## Production deployment checklist (existing open-access architecture; names only, no values read or printed)
Inspected: `.env.example`, `backend/core/config.py`, `render.yaml`, `docker-compose.yml`, `deploy/README.md` and `deploy/env`, `EIMS_OPERATIONAL_HANDOFF.md`. Nothing was changed and no live environment was inspected.
| Area | Finding | Status | Owner action |
|---|---|---|---|
| Environment and secret names | `EIMS_ENVIRONMENT`, `EIMS_DB_*`, `EIMS_REDIS_*`, `EIMS_JWT_SECRET_KEY`, `EIMS_ADMIN_TOKEN`, `EIMS_ADMIN_PASSWORD`, `EIMS_AUTH_MODE`, `EIMS_MINIO_*`, `EIMS_DB_IDENTITY`, `EIMS_DB_IDENTITY_REQUIRED`; `render.yaml` also lists `EIMS_DEMO_SOFT_DEPS`, `EIMS_DEMO_PUBLIC_ACCESS` (demo switches, must not be set for production) | documented | set real values in the secret store |
| Boot guard | outside `development` the process refuses to start while the database password, MinIO secret, JWT secret or admin token still equal the development defaults, if `ADMIN_PASSWORD` is unset, or if `AUTH_MODE` is `demo` | present in code | confirm production uses `EIMS_AUTH_MODE=secure`; this does not add a login (open-access identity still applies) |
| Secret storage and rotation | the repository holds only an example template; no rotation procedure found | NOT VERIFIED | define the secret store, rotation interval and owner |
| Database boundary | `deploy/sql/01_roles.sql`, `02_runtime_grants.sql`: separate migration (owner) and runtime roles; runtime cannot update/delete append-only audit and verification tables; proved on disposable PostgreSQL by `tests/test_privilege_topology_pg.py`; bundle marked "PREPARED, NOT APPLIED" | prepared, not applied | apply to the production database through the migration role; set role passwords from the secret store |
| Synthetic vs production data | tests run only against disposable loopback databases with an allowlist guard; the `catalog_import` tool refuses non-loopback, standard-port or non-allowlisted databases | enforced in tooling | never point test tools at production; keep the disposable containers separate |
| Backup and restore | handover notes record a logical backup/restore drill on a synthetic database; WAL/PITR, retention, measured RPO/RTO and offsite backup are listed as not established | NOT VERIFIED | Operations to establish and witness a restore |
| Monitoring and health | `/api/v1/health` and `/api/v1/ready` (the latter used by `render.yaml`); Prometheus/Grafana in the compose stack (development stack) | endpoints present; production alerting NOT VERIFIED | define alerts and ownership |
| Audit log retention | audit table is append-only for the runtime role; a retention policy is not defined | NOT VERIFIED | define retention and archiving |
| Governance write authorization | reviewer capability plus gates, tested | verified (tests) | grant the reviewer flag through the admin API to named people only |
| Network exposure and TLS | compose publishes development ports; no production TLS/ingress configuration was inspected; the handover notes TLS/secrets as open items | NOT VERIFIED | terminate TLS at the production ingress; do not expose database, Redis, MinIO, Grafana or Prometheus ports publicly |
| Operational recovery procedure | no production runbook was inspected | NOT VERIFIED | write and rehearse one |
Production Readiness stays PARTIAL until these are verified with deployment evidence and the owner accepts operation.

## Remaining human actions
1. Owner: decide whether a three-reviewer rule is wanted (default: keep the existing gates).
2. Owner: find qualified independent reviewers per the criteria; create their reviewer accounts through the admin API once they are identified.
3. Reviewers: read the original Cisco pages (ASA 113005 plus five pages), fill the worksheets independently, then record decisions through the reviewer workflow.
4. Owner/Operations: complete the production checks above.

## Files in this pass
Changed: `reviewer_sourcing_and_qualification_report.md` (policy table, evidence categories), `asa_113005_review_package.md` and `cisco_five_page_review_assignments.md` (worksheet headers: record key, source, scope, question, competencies, risk/recovery, independent conclusion, identity, declaration, source-access status). Added: this report. No source code, test or data file changed. Previous reports (`final_acceptance_report.md`, `browser_acceptance_report.md`, `reviewer_ui_acceptance_report.md`, `remediation_research_final_report.md`, `end_to_end_final_report.md`) are unchanged in this pass and remain accurate.

## Tests
Run in this pass: none (documentation only; counts re-derived from the committed eligibility artifact: 911 / 1 / 42 / 868). Not rerun, and why: backend regression, analyzer-PG, browser cases, TypeScript and build, because no source changed since the evidence above; the 16-record research, because it is complete for this scope.
