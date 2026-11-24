# EIMS V12 — A13 Test Isolation Design

Date: 2026-11-18 (Asia/Bangkok)
Finding: EIMS-F1 — a unit test reached the operational stack (`eims-postgres`, `eims-redis`, `eims-minio`).

## 1. Root cause

The A12 guard was a **port denylist**: it refused 5432/6432/6379 on loopback and accepted anything else. That cannot distinguish a disposable instance from a tunnel or a remapped operational service. It also ran only in the `client` fixture, not at every lifecycle entry point.

## 2. Implemented contract (A13.2)

`tests/disposable_guard.py` now requires **all** of the following before any connection:

| Requirement | Environment variable |
|---|---|
| Campaign marker (well-formed id) | `EIMS_TEST_DISPOSABLE_ID` |
| Database endpoint allowlist | `EIMS_TEST_ALLOWED_DB_ENDPOINTS` |
| Database name allowlist | `EIMS_TEST_ALLOWED_DB_NAMES` |
| Database role allowlist | `EIMS_TEST_ALLOWED_DB_USERS` |
| Redis endpoint allowlist | `EIMS_TEST_ALLOWED_REDIS_ENDPOINTS` |
| Redis db index minimum (and never 0) | `EIMS_TEST_ALLOWED_REDIS_DB_INDEX_MIN` |
| MinIO endpoint allowlist | `EIMS_TEST_ALLOWED_MINIO_ENDPOINTS` |
| MinIO bucket prefix allowlist | `EIMS_TEST_ALLOWED_MINIO_BUCKET_PREFIXES` |
| Schema prefix allowlist (when `EIMS_TEST_SCHEMA` is set) | `EIMS_TEST_ALLOWED_SCHEMA_PREFIXES` |

Hard refusals regardless of allowlist: `eims_registry`, `eims_user`, ports 5432/6432/6379.

The guard validates the **settings the application will actually use**, not an intent variable. Missing configuration ⇒ skip before the lifespan starts.

## 3. Coverage

Guarded at:

- `tests/conftest.py` `client` fixture
- `tests/test_auth_modes.py` (2 sites)
- `tests/test_analyzer_investigation.py`
- `tests/test_analyzer_reliability.py`
- `tests/test_analyzer_integration_stability.py`

A repo-wide test asserts that every `with TestClient(app)` has the guard within its preceding block, so a new bypass fails CI.

## 4. Verification (offline, no service started)

| Check | Result |
|---|---|
| Contract suite | **18 passed** |
| Default settings (operational) | **skipped before connection**, 0 `Connecting to Redis` lines |
| Operational DB name allowlisted | **refused** |
| Operational role allowlisted | **refused** |
| Operational port allowlisted | **refused** |
| Redis db 0 | **refused** |
| MinIO operational bucket | **refused** |
| Valid disposable identity | **accepted** |

## 5. Residual limits

1. The allowlist is configuration; an operator can add an operational endpoint. It is now a visible, reviewable act, not a silent default.
2. The guard covers the app lifespan and TestClient entry points. Integration tests that build their own engines must call the same guard; `incident_db_support.py` still uses its own marker policy and should be unified (open).
3. Object-store writes by tests that bypass the app (direct boto/minio clients) are not intercepted.
4. It is a guard, not a sandbox.

## 6. Rule going forward

No test may run against a service whose identity was not proven disposable by the contract above. Tier-2 tests require a separate approval to start disposable services.
