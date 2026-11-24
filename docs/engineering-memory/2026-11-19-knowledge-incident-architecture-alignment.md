# 2026-11-19 — Knowledge Foundation / Incident Core architecture alignment

Status: implemented and tested on disposable PostgreSQL; **not accepted** (human review, runtime integration with the other workstream's backend, and bundle-path browser E2E outstanding). Full detail: `docs/knowledge/ARCHITECTURE_ALIGNMENT_20261119.md`; chronological log: `docs/knowledge/KNOWLEDGE_FOUNDATION_EXECUTION_CHECKPOINT.md`.

```
Diagnostic Knowledge Catalog ──► Analyzer retrieval (knowledgeMatch) ──► Incident Core
   (canonical + review overlay)        trust classification                (hypotheses, evidence,
        ▲                                                                   confirmation, remediation,
        │                                                                   verification, resolution)
        │ approved only                                                          │ completed incident,
        └──────────── Knowledge Review (existing lifecycle) ◄───────────────────┘ confirmed root cause:
                      pending → independent reviewer                              human-authored proposal
```

Rules kept: no second catalog; no automatic promotion; no application login; unattributed / shared-token actors can never confirm, verify, resolve or close; snapshots of knowledge at time of use are historical and never rewritten.
Migrations this round: `d4f7b0a2c503`. Tests: see checkpoint (combined run 364 passed, 1 failed: obsolete login assertion).
