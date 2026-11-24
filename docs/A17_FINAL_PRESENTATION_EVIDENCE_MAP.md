# A17 — Final Presentation Evidence Map

**Date:** 2026-11-19 · EIMS only. Do not mention Chat_HAND in presentation content.

Every claim below is either approved (backed by the audit) or prohibited.

## Approved claims

| Claim | Backing evidence | Limits |
|---|---|---|
| "EIMS integrates asset management, telemetry ingest, incident processing and log analysis." | `backend/api/routers/**`, `backend/domain/{asset_registry,telemetry,incident,analyzer}/**`; runtime wiring in `backend/main.py` | None material |
| "Selected workflows include automated validation and safety controls, with documented limitations." | analyzer upload/parse guards, incident reviewer gate, approval-gated tooling | Do not enumerate controls that are absent |
| "The analyzer ingests, normalizes, persists and correlates events into incidents with evidence references." | analyzer services + incident correlation; 114 offline tests; prior DB integration for v1.1 | Say "selected events", not "all Windows event types" |
| "Incident evidence is idempotent per source identity." | `UNIQUE(source_type, source_id)` + service evidence lookup; tests | No cross-transaction atomicity claim |
| "Database trust and authorization controls are partially implemented and explicitly scoped." | R-1/R-3 status | Must be stated, not implied complete |

## Claims requiring qualification

| Claim | Required wording |
|---|---|
| Search/timeline | "implemented; correctness verified by inspection, not by live acceptance" |
| AI enrichment | "uses an external model; outputs are advisory and not authoritative" |
| Dashboard | "implemented; not exercised in this audit" (no service started) |
| USB auditor | "packaged client; processes collected records — not a live monitor" |
| Benchmark | **Excluded.** If asked: "present but excluded from claims; target safety is name-only" |

## Prohibited claims

- "Production-secure" / "security accepted" / "enterprise-hardened".
- "Tamper-proof audit" or "tamper-evident audit".
- "Gateway enforces authorization".
- "Maintenance CLI is SAFE-DISABLED" (it is enabled).
- "Benchmark target fully verified".
- "Full database identity verification".
- "All tests passing means security acceptance passed".
- "Operational acceptance" without operational evidence.
- Any claim that a missing artifact (`risk-policy.mjs`, journal,
  `test_a17_closure_behavior.py`) is implemented.

## Demo scope

Recommended demo path (all read-only or synthetic):

1. Asset registry list/detail.
2. Analyzer: submit a synthetic event bundle → history row → incident with evidence.
3. Incident detail: severity, status, evidence references.
4. Search/timeline over the seeded synthetic data.
5. Limitations slide: DB trust, authorization, destructive tools excluded.

Do **not** demo: benchmark, maintenance CLI, seed scripts, `clear_db.py`,
gateway authorization (absent), journal (absent).
