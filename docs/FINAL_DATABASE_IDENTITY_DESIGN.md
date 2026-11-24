# EIMS — Database Identity Design (R-1)

**Date:** 2026-11-19 · HEAD `85493b2`

## 1. Threat model

- The untrusted party is the **caller** (API request, tool invocation), not the process owner.
- Process configuration (`EIMS_DB_IDENTITY`) is trusted because it is set before start-up
  by the operator; request data never reaches it.
- A URL, hostname, database name or database-name suffix is **not** evidence: it describes
  intent, not the connection the statement will run on.

## 2. Two separate policies (never merged)

| | Policy A — application runtime | Policy B — disposable / destructive tools |
|---|---|---|
| Applied at | `database_engine.get_session()` — the single dependency every API request uses | `require_destructive_target()` on the same transaction as the mutation |
| Accepted evidence | live row (`current_database`, `current_user`) must equal `EIMS_DB_IDENTITY="db\|role"` | same live row; also accepts a database comment starting `EIMS-DISPOSABLE-` |
| Sentinel | **never** authorizes application CRUD | one input among the proof, and only for tools |
| Missing config | `EIMS_DB_IDENTITY_REQUIRED=1` → fail closed; otherwise the session is marked `unconfigured` and a one-time WARNING is logged (there is no readiness endpoint yet) | always fails closed |
| Scope | every request session, before the caller can execute a statement | clear_db (now retired), session cleanup, seed purge, benchmark truncate |

The sentinel is deliberately weaker than deployment configuration and is never a
substitute for it.

## 3. What is actually verified

`connection_identity()` executes, on the live session:

```sql
SELECT current_database(), current_user, session_user, shobj_description(oid,'pg_database')
FROM pg_database WHERE datname = current_database()
```

`current_user` vs `session_user` are both recorded: a `SET ROLE` changes the effective
role, and the policy compares `database|current_user`.

## 4. Enforcement point and bypass analysis

| Path | Covered? |
|---|---|
| API request sessions (`Depends(get_db_session)`) | **Yes** — the guard runs before `yield` |
| Background workers via `get_session_maker()` | **No** — they construct sessions directly; documented gap |
| Direct `create_async_engine(...)` (tests/tools) | **No** by design; tools use Policy B explicitly |
| Raw DBAPI access | **No** — no supported path uses it |
| Reconnect / pool reuse | The check binds to the session's connection at acquisition; a session that releases and re-checks out another connection is **not** re-verified. Documented residual. |

No claim is made that a single hook covers every mutation. Pool checkout events were
rejected as the primary mechanism: for async engines they run on the sync proxy and cannot
await the identity query, and a checkout check does not survive a later reconnect.

## 5. Deployment

```dotenv
# required for a compliant deployment
EIMS_DB_IDENTITY=eims_registry|eims_app
EIMS_DB_IDENTITY_REQUIRED=1     # missing/malformed config fails closed
```

Operator determines the expected value by connecting with the application role and
running `SELECT current_database(), current_user;` — never by copying the URL.
Malformed values (not exactly one `|`, or an empty part) are rejected at the first request
session; there is no start-up validation yet, so a bad value boots healthy and then fails
every request. Failure messages name the configuration, not credentials.

Migration path for an existing deployment: deploy with `EIMS_DB_IDENTITY` unset and
`EIMS_DB_IDENTITY_REQUIRED=0` (no behaviour change, readiness reports `unconfigured`), then
set both values and restart; a mismatch then fails every request until corrected.

## 6. Failure modes

| Condition | Result |
|---|---|
| Identity query fails | request fails before any statement |
| Value mismatches role or database | request fails |
| `REQUIRED=1` and value missing/malformed | request fails |
| Value unset, `REQUIRED≠1` | allowed, marked `unconfigured` (visible, non-compliant) |
| Destructive tool without identity or sentinel | raises `MutationTargetError`, no SQL |

## 7. Status

**R-1: ENFORCED WHEN CONFIGURED; NOT CLOSED.** Not closed because no deployment has the
configuration and the worker/direct-engine paths are not covered.
