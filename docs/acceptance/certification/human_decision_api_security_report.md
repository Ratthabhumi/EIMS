# Human Decision API — security report (2026-11-22)

Code: `backend/api/routers/analyzer/knowledge_governance.py` (mounted under `/api/v1/knowledge/governance`), gate rules in `backend/domain/knowledge/gates.py`, persistence in `backend/domain/knowledge/service.py`. Tests: `tests/test_knowledge_governance_api_pg.py` (13 scenarios, real authentication dependencies, disposable PostgreSQL) and `tests/test_knowledge_gates.py` (gate rules).

## Endpoints
| Method | Path | Who |
|---|---|---|
| POST | `/governance/decisions` | `require_knowledge_reviewer` (database user + valid session + reviewer capability or admin role) |
| GET | `/governance/history?catalog_id=` | any caller the API already serves (audit trail is readable like the existing source-event history) |

## Where each identity fact comes from
| Fact | Source | Client can influence it? |
|---|---|---|
| Actor ID | the authenticated principal returned by `require_knowledge_reviewer` | **No** (body field `actor` and nested `review.verifier/reviewer/...` are rejected with 422; `extra="forbid"`) |
| Actor kind | set to `human` by the server after the reviewer dependency succeeds, persisted in the event evidence | **No** (`actor_kind`/`actorKind` rejected) |
| Authority | `User.knowledge_reviewer` or `role == admin` in the database | No |
| Record version | the current canonical content hash; a different hash returns 409 with the current hash | The client must *prove* it saw the current version |
| Scope | server checks the approval scope against the record class (B diagnostic, C/E/F reference, D state reference; Windows context has no approval) and, for a diagnostic approval, that every operational section is stated | Client chooses among allowed values only |

## Refused callers (tests)
anonymous (401), shared `ADMIN_TOKEN` (403: a shared secret is not a person), forged/unsigned JWT (401), unknown user (401), valid user without reviewer capability (403); automation and AI have no account type that reaches this endpoint, and the service/gate refuse `actor_kind` of `ai_assist`, `automation`, empty or unknown for source_verified, validated, approved, deprecated and superseded (42 gate cases + a PostgreSQL service test). A decision made before a content change cannot carry forward (hash mismatch → 409; earlier source_verified bound to old content → 422). Approval needs a different human from the verifier and validator (403) and the contributor/self-approval rules remain.

## Audit trail
Append-only `knowledge_review_event` (database trigger blocks UPDATE/DELETE): actor, `actor_kind`, rationale, source hash, revision, evidence references, approval scope, record class, replacement id for supersession. The history endpoint returns events in order and a `stale` flag when the stored hash differs from the current content. Registration by the catalog adapter is attributed to automation (`catalog_import`), is never a decision and cannot satisfy a prerequisite of a later decision.

## Mutation check
With the server-set verifier and the forbidden-key list removed, 5 tests failed; the code was restored. The tests are sensitive to the controls they claim to test.

## Residual risks (stated, not hidden)
1. The system cannot prove that the person behind a reviewer account is not delegating to a tool; `knowledge_reviewer` is an explicit grant by an administrator, and that grant is the authority. A separate `account_kind` for automation accounts would need a migration and an owner decision.
2. There is no reviewer UI and no role/authority hierarchy beyond "reviewer or admin"; scope-specific authorities (e.g. only a DBA may approve PostgreSQL records) are not modelled.
3. Reviewer identity is the username; if an account is renamed or deleted the history keeps the old string.
4. The decision API covers the 911 catalog records only; `KnowledgeEntry` approvals keep their own existing workflow.
5. `actor_kind` lives in the event JSONB; a queryable column/CHECK constraint is a future migration (none was created or applied).
