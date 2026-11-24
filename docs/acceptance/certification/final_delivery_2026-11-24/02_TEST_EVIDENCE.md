# Test Evidence — Unified Catalog Delivery Pass

**Date:** 2026-11-22  
**Command:**

```text
.\venv\Scripts\python.exe -m pytest ^
  tests/test_unified_catalog.py ^
  tests/test_diagnostic_catalog.py::test_catalog_api_filters_and_history_totals ^
  tests/test_diagnostic_catalog.py::test_exact_windows_preservation_and_counts ^
  -q --tb=short
```

**Result (contract suite):** `.....` **5 passed**, exit code **0** (earlier combined run).  
**Re-check after `count_semantics` note:** `tests/test_unified_catalog.py` → **3 passed**, exit **0**.

| Test | Result |
|---|---|
| `test_identity_claims_machine_verifiable` | PASS |
| `test_list_filters_reconcile_to_rows` | PASS |
| `test_api_endpoints` | PASS |
| `test_catalog_api_filters_and_history_totals` | PASS (prior combined run) |
| `test_exact_windows_preservation_and_counts` | PASS (prior combined run) |
| Browser Catalog UI vs live API | **PASS** — see `05_BROWSER_VERIFICATION.md` |

**Not run this pass:** full pytest suite, full product browser E2E journeys A–H, Analyzer-PG full file, production health probes.

**Latest current-status result (2026-11-22):** `tests/test_unified_catalog.py` — 4 passed, exit 0; `node scripts/check-catalog-ui-labels.mjs` — OK. These are the current-register results; the 5-test combined run and 3-test re-check above remain earlier evidence. This document was reconciled after the current focused rerun.  

**Identity evidence artifact:** `catalog_identity_evidence.json`  
Values: governed 911 · matchable 181 · other 730 · class B 39 · B∉load_catalog 11 · eligible 1 · blocked 42 · ineligible 868 · human_approved 0 · strict_subset true
