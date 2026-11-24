# EIMS Final Independent Acceptance Review

Date: 2026-11-19
Reviewer: separate read-only agent session (Claude Code CLI, `Read`/`Glob`/`Grep`
only, `--no-session-persistence`), **not** the implementation author.
Method: two adversarial passes over the final source, migration and tests.
This is an AI reviewer, not a human sign-off.

## Pass 1 — full scope

Scope: resolution invariant, persisted verification, append-only history, API
wiring, engine-level DB identity, evidence/digest handling, concurrency,
direct-bypass paths, and test quality.

Verdict: **ACCEPTED WITH LIMITATIONS**, with these findings:

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | HIGH | Raw `UPDATE incidents SET status='resolved'` bypassed the service invariant | Fixed: PostgreSQL resolution trigger |
| M2 | MEDIUM | Raw SQL could bypass identity/verification elsewhere | Covered by M1 + append-only triggers |
| M3 | MEDIUM | Concurrency relied on Python checks (historical) | Fixed earlier: `FOR UPDATE` + single commit |
| M4 | MEDIUM | Cycle staleness relies on timestamps | Accepted limitation; documented (clock skew risk) |
| M5 | MEDIUM | Append-only was UPDATE/DELETE only; TRUNCATE allowed | Fixed: BEFORE TRUNCATE statement trigger |
| M6 | MEDIUM | Verifier could verify their own evidence | Fixed: `verifier_conflict` |
| L1 | LOW | Unique key is `(incident, cycle, evidence)`, not `(incident, cycle)` | Accepted limit; documented |
| L2 | LOW | `FOR UPDATE` without `populate_existing` | Fixed |
| L3 | LOW | Non-canonical `source_id` (`01`, `+1`) | Fixed |
| L4 | LOW | Asset check skipped when either side is NULL | Fixed (strict) |
| L5 | LOW | "analysis proves remediation" is a reference check | Accepted limit; documented |
| L6 | LOW | Migration triggers not exercised via a migrated schema | Accepted limit; documented |
| L7 | LOW | `_detail()` failure after commit returns 5xx | Accepted limit; persisted state is authoritative |

## Pass 2 — targeted re-review of the fixes

The four fixes plus the service insert-before-update ordering were re-read.
Result: "Of the four fixes, I found no HIGH defects and one MEDIUM item."

- Resolution trigger present in the migration and in the test installer; the
  service flushes the verification row before updating status, so the
  legitimate path still works (proved by the 22-test suite).
- TRUNCATE trigger present and tested.
- `verifier_conflict` mapped to `IncidentPermissionError` (403).
- Canonical-id and strict asset-match checks behave as intended.
- Remaining MEDIUM: an oversized all-digit `source_id` raised a raw `DataError`
  (fail-closed but a 500). **Fixed** afterwards (`source_pk > 2**31-1` →
  `evidence_source_malformed`) and re-run.

Final verdict line from the reviewer: `VERDICT: ACCEPTED WITH LIMITATIONS`.

## Claims tested and upheld

| Claim | Evidence |
|---|---|
| No supported path resolves without a persisted verification | service tests 1-11, raw-SQL trigger test, `grep change_status` shows one service + one controller call site |
| A caller cannot forge verification fields | request schema `extra="forbid"` (3 validation tests); verifier derived from auth |
| Foreign/corrupted/wrong-type evidence is rejected | tests 4-8 |
| Previous-cycle evidence is rejected after reopen | test 7, 14, E2E steps 12-15 |
| Concurrent resolve/reopen cannot produce an invalid state | tests 13-14 with persisted-state assertions |
| Failed verification persistence rolls back the transition | test 15 (real unique violation) |
| ORM/Core/text use the same guard; no raw-engine bypass | 9 API identity tests + source scan |
| HTTP cannot mutate the wrong DB/role | wrong-DB/wrong-role HTTP cases with row counts |
| Append-only history resists UPDATE/DELETE/TRUNCATE | trigger tests |
| Tests fail if the service invariant is removed | asserted persisted status/cycle/count in every denial |

## Limitations carried forward

1. Recurrence ordering in `_reuse_incident` is not exhaustively proved.
2. Verification proves persisted reference integrity, not external system health.
3. Separation of duties is one-directional (any authenticated user may attach
   evidence; the verifier may not verify their own).
4. Triggers guard `UPDATE`/`DELETE`/`TRUNCATE`, not a raw `INSERT` of an
   already-resolved incident or a fabricated `passed` row.
5. A runtime role that owns the tables could disable triggers; production must
   run as a non-owner with least privilege (deployment step, not implemented).
6. Enforcement is at the engine facade; a raw engine handle bypasses it.
7. Disposable PostgreSQL only; no live deployment verification.
8. Ingest worker integration suite not run (missing Redis/sentinel env).

## Decision

**Independent final acceptance: ACCEPTED WITH LIMITATIONS.**
No unresolved HIGH finding in the accepted scope. Limitations 1-8 are recorded
in `EIMS_FINAL_DELIVERY_STATUS.md` and must be carried into operations.

## Round 3 — security & deployment closure

A third read-only pass reviewed the runtime-identity startup hardening, the
privilege topology, the new DB guards, the deploy bundle and the excluded
subsystem dispositions.

First result: **NOT ACCEPTED**, with one HIGH and several MEDIUM findings:

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| S1 | HIGH | `deploy/sql/*` was never executed; it used psql variables inside `DO $$` blocks (invalid), provisioned roles before migrations, and granted nothing to the migration role | Fixed: split into `01_roles.sql` (pre-migration) and `02_runtime_grants.sql` (post-migration), plain SQL with `current_setting`, no psql meta-commands. The privilege suite now executes both scripts verbatim against a throw-away database |
| S2 | MEDIUM | Raw `INSERT` could create an already-resolved incident | Fixed: `BEFORE INSERT` state guard (tested at service-schema and runtime-role levels) |
| S3 | MEDIUM | The resolution trigger accepted any verification row; evidence ownership/digest/verifier were not required at the DB level | Fixed: trigger now joins `incident_evidence` and requires same incident, matching digest, verifier ≠ evidence author, current-cycle freshness |
| S4 | MEDIUM | Negative privilege tests asserted only `DBAPIError` | Fixed: each case asserts its expected denial fragment (`permission denied`, `must be owner`, `cannot be resolved without verification`, `may only advance`) |
| S5 | MEDIUM | CREATE revocation was not tested against the real schema; `PUBLIC` retained CREATE | Fixed: script revokes CREATE from `PUBLIC`; the test runs on the script-managed schema |
| S6 | MEDIUM | Startup depended on a database connection even when identity was unconfigured | Fixed: live verification only runs when identity enforcement is expected; unconfigured dev stays lazy and is reported `unconfigured` |
| S7 | LOW | `EIMS_DB_IDENTITY_REQUIRED` accepted only the exact string `1` | Fixed: strict parser (`0/1/true/false/yes/no/on/off`), anything else is a config error |
| S8 | LOW | `create_tables.py` used a raw engine handle | Fixed: uses `database_engine.connect()` + `verify_runtime_identity()` |
| S9 | LOW | Docs still said startup did not validate identity; worker wording implied a separate binary | Fixed in `DB_RUNTIME_IDENTITY_ACCEPTANCE.md` and `deploy/README.md` |

Evidence after the fixes: 137 focused tests + 15 privilege-topology tests, all
passing; the 15 include executing the real deploy SQL, migrating as the migration
role, and denying UPDATE/DELETE/TRUNCATE on verification, trigger
alter/drop/disable, DROP FUNCTION, CREATE TABLE, `session_replication_role`,
`SET ROLE`, raw resolve, raw resolved-insert, and cycle rewind.

Remaining accepted limitations are unchanged and recorded in
`EIMS_FINAL_DELIVERY_STATUS.md` (notably: a fully compromised runtime credential
could still insert an internally consistent verification row).

### Round 3 outcome

A second targeted pass on the fixes returned **NOT ACCEPTED** with one remaining
MEDIUM: `closed` was not treated as terminal by the DB guard, so
`resolved -> closed -> open -> resolved` could replay an old verification. It
also noted untested revokes (audit_logs, incident_evidence, alembic_version).
Both were fixed:

- the cycle guard now rejects any exit from `closed`;
- four denial cases and the full resolution write set (evidence + verification +
  status as the runtime role) were added to the privilege suite (24 tests).

Final targeted verdict: **ACCEPTED WITH LIMITATIONS**. Security/deployment round
3 is accepted at code and disposable-PostgreSQL level; whole-system security and
live deployment remain NOT ACCEPTED / NOT PERFORMED.

### Round 4 — deployment topology and verifier decision

A fourth read-only pass reviewed the topology claims, the PgBouncer findings and
the verifier decision. It found over-claims rather than code defects, and they
were corrected:

- the CVE/version advisory list was presented as sourced fact — now explicitly
  marked **unverified** (confirm against official release notes and the pinned
  digest);
- the PgBouncer test claimed a `pg_backend_pid()` reuse proof it never made — it
  is now an honest, **never-executed harness** that proves the identity guard
  through a pooler, not pid reuse;
- the "journal is INSERT-only" claim ignored `ALTER DEFAULT PRIVILEGES` — the
  grant script must be **re-run after every migration**, now stated in the
  script, the runbook and the topology document;
- compose findings were incomplete — public MinIO bucket, all-interface port
  publishing and unpinned images are now recorded;
- the `SECURITY DEFINER` rejection now states its two independent grounds.

Round 4 verdict: **ACCEPTED WITH LIMITATIONS**. The remaining limitations
(compromised runtime credential, unverified pooler, no target environment) are
the reason the overall delivery stays **NOT READY**.

