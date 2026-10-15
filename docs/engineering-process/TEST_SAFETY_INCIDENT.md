# Test safety incident — 15 October 2026

## Observation and impact

An overly broad validation command included the pre-existing `tests/test_auth_modes.py` before its operational dependencies were fully inspected. That file used `TestClient(backend.main.app)`, starting the real application lifespan, and performed evaluation-session POST requests against the configured database. A read-only query scoped to the exact synthetic test titles, customer labels and test-run time window confirmed **three synthetic service-session rows**. This was a test-isolation mistake; it was not authorized workplace data modification and must not be described as a hermetic validation.

No rows were automatically deleted or restored. Exact record identifiers/timestamps are retained in a private local incident report, outside Git. No company/customer row contents are published. There is no pre-run database snapshot; other startup/worker effects cannot be conclusively excluded. The existing application lifespan includes bootstrap checks and workers, so this report does not assert that the three rows are the only possible side effects.

## Containment and correction

- The unsafe run finished and is excluded from the final isolated pass count. No further real application TestClient runs are used.
- The auth suite now overrides application lifespan with a no-op context, fails if operational database initialization is attempted, provides in-memory session persistence, and replaces the auth module's direct session generator with an in-memory generator. Non-admin lookups still execute the real authorization logic against an empty synthetic user result.
- Analyzer route regressions use a minimal FastAPI app and fake sessions; the 207-test repaired Analyzer/upload/config run passed separately without an operational application lifespan.
- Live service containers were not restarted, credentials were not changed and no cleanup/rollback was performed.

## Owner follow-up

Review the private incident report and the three exact synthetic rows. Any selective removal requires separate authorization and a checked dependency/backup plan; no blanket cleanup or database reset is proposed. Review startup/worker logs privately if needed. Do not count this incident or its synthetic service-session records as real user evaluation or as verification of Analyzer persistence.

The agent disclosed the mistake during the task. Final engineering evidence must distinguish corrected isolated results from the earlier unsafe run.

## Follow-up, without operational access

The consolidation continuation did not query or modify the three affected records. Exact IDs/time window and the existing read-only checker remain in the private backup. Owner procedure: review AUTH_TEST_SIDE_EFFECTS_PRIVATE.json, then use parameterized SELECT scoped to those exact session IDs and the recorded time window. Compare synthetic labels and dependent references privately; do not publish rows or use a broad name-only deletion. A cleanup proposal is limited to those three confirmed rows after a backup/dependency review and separate owner authorization. No DELETE/UPDATE/reset was executed. New real persistence checks use a guarded SQLite-only harness with no operational app lifespan; this does not retroactively erase the incident or rule out earlier unknown startup effects.
