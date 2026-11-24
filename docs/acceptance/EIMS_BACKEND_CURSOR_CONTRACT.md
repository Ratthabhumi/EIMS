# Backend <-> Cursor contract, version 3 (2026-11-20, supersedes nothing; extends `2026-11-20-claude-backend-contract-for-cursor.md`)

Migration head: **`c9f4a7b0d826`**. Cursor owns the UI; no frontend files were touched.

## Runtime to test against
`tools/run_isolated_backend.sh start|status|stop` -> `127.0.0.1:8031`, database `eims_cursor_accept` (disposable, non-superuser role). Set `EIMS_BACKEND_URL=http://127.0.0.1:8031`, run `status`; all checks must PASS before a browser run. (Port 8032 is used by the backend E2E script, never 8000/8021.)

## Changes since version 2
1. **Event time on evidence** (`incident.evidence[]` / `summary.correlation.time`): `{ event_time|null, time_basis, time_confidence: exact|asserted|ambiguous|missing, time_original, ingestion_time_is_not_event_time: true }`. Show "event time unknown / ambiguous" instead of the request time. `time_basis` examples: `xml_timecreated_systemtime`, `source_timestamp_explicit_zone`, `source_local_with_declared_zone`, `local_time_without_zone`, `local_time_day_month_order_unclear`, `local_time_ambiguous_dst_overlap`, `local_time_nonexistent_dst_gap`, `timestamp_in_the_future`, `malformed_timestamp`, `no_timestamp`, `offline_import_time_absent|source_naive`.
2. **`match: ambiguous_not_merged`** now also occurs whenever event time is untrusted; `summary.correlation.candidates[].reasons` contains `event_time_untrusted:<basis>`. Pasted Event Viewer text (`Date: 11/20/2026 9:14:22 AM`) has no zone and unclear day/month order, so it is never time-correlated; explain this to the engineer, do not retry/merge client-side.
3. **Knowledge provider scope**: knowledge entries/proposals expose `provider`, `providerScope` (`provider_specific|vendor_product|generic|unknown|unverified`). `GET /api/v1/knowledge?provider=` filters. Approval of a Windows entry without a provider returns `422` ("Provider attribution is required"). Summary evidence lines include `Approved-knowledge match: provider_exact|vendor_identity|generic_context`; `generic_context` is contextual, never a provider-specific diagnosis.
4. **Windows Event XML**: pasted XML (`TimeCreated/@SystemTime`, `Provider/@Name`, `EventRecordID`) is parsed structurally (defusedxml); `eventMetadata.attributes.timeSource = "xml:System/TimeCreated@SystemTime"`, `recordId`.
5. **Curated Windows guidance** now comes from the canonical catalog; corrected text for Event 5011 and 109. Contract fields of `SolutionSummary` unchanged.
6. **Health semantics** (unchanged codes): `/api/v1/health` 503 `DEGRADED` when any tier is down; `/api/v1/ready` (DB-only) for load balancers. Redis is required only for telemetry streams/alerts and the incident-ingest *stream* (outbox rows stay pending, nothing lost); HTTP analyze, incidents, notes, workflow and knowledge do not need Redis.

## Unchanged and still authoritative
Notes API (`POST/GET /incidents/{id}/notes`, server-derived actor/assurance), diagnosis/remediation/verification/resolve rules (resolve needs verified identity + verification evidence), audit timeline (`/workflow-events`), knowledge proposal (`/incidents/{id}/knowledge-proposals`, always pending).

## Distinguish these empty/failed states in the UI
404 route missing (stale backend: run `status`) | 401/403 permission | 409/422 rule violation (show `detail`) | 503 dependency | empty list = data absent. Never render a failed call as an empty success.

## Still Cursor's to prove
Browser E2E against the isolated runtime: Analyze -> Analysis Details stays open (no forced Incident jump), Incident Workspace, Notes persistence after reload, ambiguous outcome display, event-time display, USB Auditor remove by record ID.

## Addendum (final gate, 2026-11-20)
* No application login: `/auth/login` -> 410; no token needed for ordinary use; `/auth/session` returns `{username:"demo", mode:"open_access", application_login:false, capabilities}`. Treat `demo` as unattributed, never as a verified person.
* Dashboard WebSocket `/api/v1/ws/dashboard`: the browser `Origin` must be in `EIMS_CORS_ORIGINS` (default includes `http://localhost:3000`, `http://127.0.0.1:3000`); other origins are closed with 1008 before accept. With `EIMS_AUTH_MODE=secure` a handshake without Origin is also refused.
* Obsidian export is owner-scoped (404 for another owner's history id).
* Decided by the user: asset/telemetry/evaluation destructive and ingest routes stay anonymous-callable (trusted network boundary is the control); the USB Auditor remove flow may rely on this. Never expose the backend beyond that boundary.
* Redis: use `EIMS_REDIS_HOST=127.0.0.1` locally.
