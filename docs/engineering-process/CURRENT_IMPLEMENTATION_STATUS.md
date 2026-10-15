# Current implementation status

Evidence basis: source review of baseline 8c26f03 plus newly measured checks in ENGINEERING_TEST_REPORT.md. Historical claims do not become new test results.

| Capability | Status | Evidence / boundary |
|---|---|---|
| Multi-vendor classification/parsing | Implemented; synthetic regression evidence | services/source_classify.py, parser.py, panos_parser.py; bounded documented formats |
| Catalog | Implemented, static contents counted | operational_event_catalog.json 141 + diagnostic_knowledge_catalog.json 22 = 163; not 163 validated incidents |
| Evidence provenance/correlation | Implemented; pure helper and synthetic route tests available | evidence.py, bundle.py, analyze.py; original file/line; association is not causality |
| History persistence/retrieval | Implemented; live verification not rerun | models/history.py, routers/analyzer/history.py; JSON solution/metadata; no new live DB claim |
| Deterministic vendor knowledge / RAG / optional AI | Implemented with bounded knowledge and optional external calls | vendor_knowledge.py, catalog_diagnostics.py, summary.py, vector_db.py; retrieval is not ground truth |
| Portable endpoint collection/import | Supporting workflow, separate | clients/usb_auditor and endpoint import; target physical USB scan → import remains unverified in this continuation |
| API/browser integration | Requires isolated end-to-end confirmation | Component mocks cannot prove live API/database persistence |
| Human-centered design/evaluation | Prepared, not executed with users | Evaluation templates; no interview, participant or result invented |
| File-copy/exfiltration determination | Research only | Audit prerequisites and corroboration missing; no detection claim |

## Defects reproduced or investigated

Windows 1129 falls through a generic synthesis path; non-vendor incident unknowns contain VMware-specific CTK/VMDK language; unsupported vendor diagnoses can be assigned medium confidence by route fallback. New regression results determine fix status. Single-upload error handling and validation are reviewed in the security change. See tests/report for measured outcomes, including any NOT RUN check.

## Documentation corrections

README/enterprise PRD have a wider scope than this study. Chapter 3's formal-requirements wording is historical documentation, not evidence of an engineer interview. Chapter 4 reports earlier runtime/field observations; those are not this branch's validation. USB field statements and 49-record metrics must retain their original context and be revalidated before final submission. Prior 176 local tests and CI at older SHAs are historical only. Do not replace them with fabricated latest CI claims.
