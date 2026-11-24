# Backend contract delivered by Claude for the Cursor frontend (2026-11-20)

Branch `demo/2026-11-24` @ `3f2beea` (uncommitted work tree). Ownership: Claude = backend/Knowledge/Incident Core; Cursor = presentation. No new endpoint family and no second incident store were created; everything below extends the existing Incident Core.

## 1. Engineer Notes (answers gap #1 of `2026-11-20-automatic-incident-backend-gaps-claude.md`)

| Call | Behaviour |
|---|---|
| `POST /api/v1/incidents/{id}/notes` body `{ "text": "<1..4000 chars>" }` | `201` `{ note_id, incident_id, text, actor, actor_assurance, created_at }`. **Only `text` is accepted**: any other field (actor, actor_assurance, status, verified, root_cause_state, created_at...) returns `422`. `404` unknown incident, `409` closed incident, `422` empty/whitespace/over-length. |
| `GET /api/v1/incidents/{id}/notes?limit&offset` | Oldest first (stable: `created_at`, `note_id`), `X-Total-Count` header, `limit` 1..200 (default 50). |

* `actor` / `actor_assurance` are derived server-side from the credential: no credential -> `demo` / `unattributed`; shared admin token -> `shared-admin-token` / `shared-token`; valid user JWT -> user name / `verified-identity`. The UI must show assurance next to the actor; it must never claim a named person for `unattributed`.
* A note has no state fields and cannot confirm a diagnosis, verify a remediation or change status (tested). Do not render notes as diagnoses.
* Every note also writes an append-only audit event (`GET .../workflow-events`, `record_type: "note"`, `action: "noted"`, no copy of the text). The note table itself rejects UPDATE/DELETE/TRUNCATE (trigger).
* Migration `a7d2c5e8f604` (additive; head). Notes are durable across restarts (verified against the database, and in the HTTP restart run documented in the consolidated report).

## 2. Association outcomes (answers gap #2)

`POST /api/v1/incidents` -> `match` is one of:

| `match` | Meaning | Suggested UI wording |
|---|---|---|
| `created` | New incident, no candidate existed | "New incident created" |
| `event_already_linked` | This source record, or the same event occurrence (identical occurrence fingerprint), is already bound | "Evidence already linked" |
| `correlated_with_open_incident` | **Strong** match only: same concrete asset **and** same provider-qualified event signature inside the window, open incident | "Evidence correlated with an existing incident" |
| `ambiguous_not_merged` | **New** (`created: true`): candidates existed but none was strong. `summary.correlation.status = "ambiguous"`, `summary.correlation.candidates = [{incident_id, confidence, reasons}]` (max 5) | "Created separately - possible related incidents need your review" + link to each candidate (explicit link via `POST /incidents/{id}/evidence`) |

Behaviour change to be aware of (it is deliberate, see `2026-11-20-consolidated-claude-backend-acceptance.md`): without a resolved asset, or with a different/missing provider, or with a different Event ID, evidence is **never** merged automatically any more; it is reported as `ambiguous_not_merged` when a candidate exists. The frontend must not merge on its own.

## 3. Evidence identity (no frontend change required)

For `source_type: "analysis"` the server enriches the reference from the persisted analysis row: provider-qualified event key (`<event id>@<provider>`), the record's concrete asset (never guessed) and, only when the source has a record id or an event time, an occurrence fingerprint. A caller-supplied digest for analysis evidence is ignored. Text alone is never an identity.

## 4. Analysis evidence contract (Event 1026)

`incident.evidenceRefs[]` (additive): `{ text, sourceFile, timestamp, lineNumbers[], occurrences, lineBasis }`.

* Exact repeats of the same text in the same source with the same stated time are **one** ref with every line number and the count (never silently dropped; raw text untouched).
* `lineNumbers` are positions in the **submitted text** (`lineBasis` says so); they are not original-file offsets. Show them with that label.
* `incident.evidence[]` and `timeline[]` no longer repeat identical strings; the UI display-only dedupe can be removed in favour of these refs.
* `event metadata.attributes` for .NET Runtime events now include `application`, `frameworkVersion`, `exceptionInfo`, `stackFrames[]` (first block, <=40, verbatim) and `exceptionBlockCount`; `faultingApp` is filled from `Application:`.
* Chronology: `timestamp` is the text as written. Do not present First/Last seen unless distinct refs have distinct timestamps.

## 5. Knowledge match (already delivered, restated)

`knowledgeMatch.matchKind` = `direct | contextual | none`, `matchBasis` explains why (`provider_and_id`, `provider_unspecified`, `provider_ambiguous`, `provider_unverified`, `provider_mismatch`, `no_record`). A `contextual` match must not be presented as a provider-specific diagnosis.
