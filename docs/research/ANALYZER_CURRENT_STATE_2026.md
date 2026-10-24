# Analyzer current execution state — 2026-10-25

## Exact source and preservation

- Remote main verified after fetch: `bf634d9ddf86f44220ef961cf4be32988cfc5ee5`.
- Existing Week 1 branch:
  `work/analyzer-week1-evaluation-2026-10-25`.
- Preparation baseline: `5655e3692434e1f93bea7d6cd9ef8b37885f48b1`.
- An isolated checkout of that same branch preserves the separate handoff
  checkout's existing deletions, demo-pack directory and untracked work.
- Production Analyzer tree and existing reliability suite are unchanged
  relative to the original main source. No company logs, HTTP runtime, History,
  operational database, USB or backup was accessed for evaluation.

## Executed before implementation

The established project virtual environment was reused, without installation
or model download. Reproduction from the isolated checkout:

```powershell
python -m pytest tests/test_analyzer_reliability.py -q -o addopts=
```

Actual result: **129 passed, 0 failed, 0 skipped, 0 errors**, 3 warnings,
3.79 seconds. Warnings: existing FastAPI/Starlette TestClient HTTPX deprecation,
existing python-json-logger module relocation, and an existing invalid escape
in a vendor-parser docstring. The last warning occurs on initial compilation;
later cached imports do not establish its removal. No warning was suppressed.
These are compatibility/documentation debt; no production repair was made.

## Runtime and optional dependency boundaries

Observed Python 3.14.3, pytest 9.1.1, Pydantic 2.13.4, FastAPI 0.141.1,
SQLAlchemy 2.0.52. Exact run environments are captured in each run's config.
`jsonschema` is available locally and declared in requirements-evaluation.txt
for fresh environments and CI. No dependency versions were silently pinned to
match an expected outcome.

`sentence_transformers` is installed; the standard Hugging Face cache probe
found zero model directories. This does not prove that no other cache exists.
No embedding model was loaded or downloaded, and no isolated vector index was
validated. Current process has no GEMINI_API_KEY; no secret value was printed,
no model/provider was contacted. M2 and M3 remain NOT_RUN, not failed models.

## Reused implementation and experimental path

Reused `parse_event_metadata`, `build_evidence_records`,
`incident_from_records`, `summarize_file_evidence`, `build_evidence_items`,
`correlate_bundle`, and (M1 only) `vendor_reference_results`. The runner imports
no router, DB session or vector module and blocks socket connections during
prediction. It never calls `build_summary`; its deterministic vendor-summary
priority therefore cannot be misrepresented as an AI-vs-rules comparison.

Existing `test_golden_veeam_acceptance_semantics` and other regression literals
remain regression evidence, not independent heldout examples. Existing search
latency tooling was not reused as a diagnostic-accuracy evaluator. No previous
complete diagnostic-accuracy corpus/evaluator was identified in scoped search.

## Validation after implementation

```powershell
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py -q -o addopts=
```

Executed **160 passed, 1 skipped, 0 failed, 0 errors**, 2 dependency deprecation
warnings, 4.65 seconds on the latest recorded run (earlier run: 2.42 seconds).
The one skip is host-refused Windows symlink creation;
the symlink test is not certified locally. The evaluation tests check empty
denominators, confusion/F1 counts, false merges/splits, exact citations versus
semantic support, hashes, traversal, normalized duplicates, scenario leakage,
frozen heldout annotations, stale review receipts, mode traces, order stability,
network/operational import guards, immutable outputs and case-error accounting.

CI now includes the existing reliability suite plus evaluation tests. CI is
separate evidence from this local execution and must be verified on the final
published commit. No unnecessary frontend, Docker or USB rebuild was run locally.

## Review and readiness boundary

Corpus: 17 synthetic DRAFT proposals, 12 dev and 5 reserved heldout. Reviewed
cases: **0**. AI-created labels were not promoted to human-reviewed status.
The dev stage pipeline executes and emits real predictions and timings, with
draft-only scores. The reviewed baseline remains **INSUFFICIENT_DATA** and
heldout remains **NOT_RUN**. See [results](../ANALYZER_BASELINE_RESULTS.md).
