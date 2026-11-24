# Draft proposal workflow report (2026-11-22)

Code: `backend/domain/knowledge/proposals.py`, endpoints in `backend/api/routers/analyzer/knowledge_governance.py`, Analyzer hook `_apply_approved_supplement` in `analyze.py`. Tests: `tests/test_draft_proposal_workflow_pg.py` (9 PostgreSQL scenarios, real authentication).

## Design (no fake history, no new table)
`KnowledgeEntry` was not used (NOT NULL FK to `analysis_history`). A proposal is a sequence of **append-only events** in the existing governance event store, keyed by `catalog_id` and the catalog **content hash**: `draft_saved`, `draft_submitted`, `draft_withdrawn`. Draft content lives in the event evidence JSONB. No schema change, no migration, nothing in `KnowledgeEntry`.

```
CANDIDATE → DRAFT → HUMAN_REVIEW → APPROVED      (also STALE, REJECTED; BLOCKED/INELIGIBLE is the adapter's eligibility, shown next to the status)
```
| Rule | Enforcement (tested) |
|---|---|
| Only human reviewers write drafts | `require_knowledge_reviewer`; anonymous 401, shared admin token 403, non-reviewer 403; body cannot name actor or kind |
| Which records | classes B, D, E only; reference-only, parser-mapped references and Windows context have no proposal path (422); unknown record 404 |
| Content is validated | same validator as the catalog loader: stated needs https source, verbatim quote, date; unverified needs a basis; placeholders rejected |
| Dry run first | `POST /proposals/preview` returns validation problems, what is missing now and with the draft, which fields are unverified; writes nothing |
| History | every save/submit/withdraw is an event with author, author kind, base hash, content digest, revision, time (append-only trigger) |
| Idempotent | saving identical content for the same base hash returns the existing draft (`created: false`, same revision) |
| Editing | a submitted draft that is edited returns to DRAFT; another reviewer may edit (both recorded) |
| Stale source | a changed catalog record makes the proposal STALE; saving or submitting with the old base hash is refused (422); a re-based draft is allowed |
| AI help | AI/automation may save a draft (recorded with its kind) but only a human may submit it; the submit event records `prepared_by_kind`; the **author cannot approve** the supplement (403) |
| Never active | the Analyzer reads only `approved_supplement`: lifecycle `approved`, content hash current, not review-required, from the approved decision event. A DRAFT, HUMAN_REVIEW or STALE proposal never reaches guidance (tested) |
| Approval | only through the decision API (human principal, hash-bound, scope by class). For a blocked class B record the diagnostic approval is checked against the record **merged with the submitted draft**; unverified or not_stated fields do not complete it; the approved supplement and its digest are stored in the approval event |
| Merge into Analyzer | stated fields of the approved supplement fill items the catalog does not state; a catalog statement is never replaced; unverified fields are never merged; review state becomes `APPROVED_SUPPLEMENT (human-approved; catalog content hash current)`; if the catalog record changes afterwards the approval is stale and nothing is merged |
Decision events (`transition`) are the only ones that count for gate prerequisites: draft events are excluded in `promote`, so saving a draft can neither reset nor satisfy `source_verified`/`validated`.

## Endpoints
`GET /governance/proposals?catalog_id=`, `POST /governance/proposals/preview`, `POST /governance/proposals`, `POST /governance/proposals/submit`, `POST /governance/proposals/withdraw`, plus the existing `POST /governance/decisions`.

## Not built (stated)
No reviewer UI for drafts (API only), no diff view of revisions, no per-field reviewer sign-off, no notification. Whether a human-approved supplement should also be written back into the catalog file is an owner decision; today it stays in the governance store.
