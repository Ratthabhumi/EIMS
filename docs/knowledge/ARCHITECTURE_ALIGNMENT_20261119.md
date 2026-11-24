# Diagnostic Knowledge ↔ Incident Core architecture alignment (2026-11-19)

## Boundaries
| Responsibility | Owner | Holds | Never holds |
|---|---|---|---|
| **Diagnostic Knowledge Catalog** (canonical JSON + sparse review overlay `knowledge_review*`) | Knowledge | Reusable knowledge: signatures, symptoms, scope, causes, steps, references, lifecycle/trust | Case-specific findings |
| **Incident Core** (`incidents`, `incident_evidence`, `incident_verification`, `incident_diagnosis`, `incident_remediation`, `incident_workflow_event`) | Incident | What happened in one incident: hypotheses, evidence links, root-cause confirmation, remediation proposed/executed, verification, actor assurance, append-only audit | Reusable knowledge definitions |
| **Knowledge Review** (existing `/api/v1/knowledge/proposals` → pending → independent reviewer) | Knowledge | Proposals and their review state | Auto-approved incident findings |

No second catalog exists. `incident_knowledge_proposal` is only a **link** (incident, confirmed diagnosis, optional executed remediation, evidence ids, proposer + assurance, diagnosis digest) to an entry that lives in the existing review lifecycle.

## Flow
```
 Diagnostic Knowledge Catalog (canonical, sparse review overlay)
        │  deterministic match + trust classification (server-authoritative)
        ▼
 Analyzer retrieval ──► solutionSummary.knowledgeMatch  (live result, History, Markdown, PDF)
        │  analysis_history_id / catalog_id (optional references)
        ▼
 Incident Core:  observation → evidence → hypothesis(es) → [verified reviewer] confirmation
        │          → remediation proposed → executed → verification → resolution/closure
        │   every diagnosis/remediation keeps a HISTORICAL snapshot of the catalog record it used
        │   (classification, review state, content hash); the CURRENT record is read separately
        ▼
 Completed incident (confirmed root cause + analysis reference)
        │  human-authored proposal; caller supplies content; nothing auto-copied
        ▼
 Knowledge Review  (existing lifecycle: pending → reviewer approve/reject; source verify → validate → approve)
        │  only reviewed + validated + approved content
        ▼
 Canonical Diagnostic Knowledge Catalog   (via the existing lifecycle, not by this link)
```

## Decisions and evidence
- **Snapshot vs current.** Diagnosis/remediation rows store the snapshot at the time of use. `GET /api/v1/analyzer/catalog/record?catalog_id=` returns the *current* canonical record and classification; the Portal shows both and states whether the canonical content hash changed. A test patches the catalog after an incident used it and shows the stored snapshot is unchanged.
- **Canonical vs incident-specific remediation.** The catalog schema has **no** remediation/verification fields (0 of 163 records). Snapshots therefore carry `canonical_remediation_available: false`, and the Portal labels every remediation "Incident-specific action". Adding catalog remediation/verification fields is deliberately *not* done here: it needs a source schema, lifecycle semantics and loader/retrieval compatibility first.
- **Trust semantics are consistent**: Analyzer, incident snapshots and the Portal all use the same classifier (`knowledge/retrieval.py`).
- **Authorisation in the domain service.** `IncidentWorkflow.confirm_diagnosis` itself requires verified-identity **and** the reviewer capability (DB lookup), not only the HTTP controller. Tested with direct service calls for unattributed, shared-token, a verified non-reviewer and a non-existent account.
- **Hypothesis rejection/supersession** keep rows (who/why/when/assurance, replacement link); confirmed rows cannot be closed; both append audit events; DB constraints forbid partial or inconsistent closure/confirmation fields.
- **Pagination**: diagnoses, remediations and events accept `limit` (1–200) and `offset`, order by `(created_at, id)`, and report the total in `X-Total-Count`; the Portal uses "Load more".
- **root_cause_state** reflects the *current cycle's live diagnoses only* (confirmed > hypothesis > unknown); reopening resets it to `unknown`.
- **Proposal preconditions** (all enforced server-side): incident resolved/closed; diagnosis confirmed by a verified-identity reviewer and in the current cycle; diagnosis references its analysis (the existing review flow requires it); evidence ids belong to the incident; the existing proposal validation/redaction and one-proposal-per-analysis rule apply. Unattributed and shared-token actors **may submit** a proposal (it is only a pending entry) but nothing here approves anything. Reviewer/validator/approver separation is untouched because review stays in the existing flow.
- **Not changed**: application login, shared-token impersonation rules, verified-identity requirement for confirmation/verification/resolution/closure, evidence digests, current-cycle verification, append-only verification history.

## Migrations
`d4f7b0a2c503` (revises `c3e6a9d1f402`): widens diagnosis status to rejected/superseded with closure columns + constraints, adds `catalog_id`/`knowledge` to remediation, creates `incident_knowledge_proposal`. Additive; downgrade verified by test (down to `c3e6a9d1f402` and up again). `c3e6a9d1f402`/`b2d5f8c0e301`/`a1c4e7b9d201` unchanged by this round.

## Human review still required
Independent human review of the Incident Core diff and migrations; human verifier/validator/approver for the 22 vendor candidates and for any knowledge proposal; decision on whether unattributed callers may reopen resolved incidents (pre-existing behaviour).
