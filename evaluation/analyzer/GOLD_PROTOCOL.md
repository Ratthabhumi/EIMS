# EIMS Gold Dataset and Baseline Protocol — v1

Purpose: reproducible, evidence-grounded accuracy evaluation, not another regression fixture suite. The source snapshot for initial assessment is bf634d9ddf86f44220ef961cf4be32988cfc5ee5.

## Corpus and provenance

Target a realistic 40–60 independently labeled incident cases, if sources and review capacity allow. Prefer ~25–35 development cases and ~15–25 held-out cases. Include Windows Event, Veeam, VMware, Fortinet and negative/unknown; note additional supported source families. Avoid overselling sample size.

Every case must have stable case_id, split, case_source (synthetic vs authorized_sanitized_field), per-file relative paths and SHA-256, expected sourceFamily, diagnosticCode or abstain, expected first and terminal failure source spans, relevant evidence spans, correlation truth (positive and negative file pairs), applicable official KB IDs/URLs with prerequisites, annotator/reviewer and status. Never place private logs, secrets, customer hostnames, credentials or proprietary third-party log samples in this public repository.

Do not classify a case as gold until it has human-reviewed annotation. A known regression fixture may be imported into dev with attribution; never into held-out. Synthetic variants of the same original incident remain in the same split. Group by incident scenario before splitting to prevent leakage. Freeze the held-out set before adapting parser rules.

## Evaluation input contract

Each case includes a manifest record and relative input file paths. Input content is immutable (verify SHA-256 before every run). Output predictions are saved by case and run configuration. Original source file / 1-based line number are the provenance units. Span matches must point to bytes/lines that actually exist and support the conclusion, not merely valid-looking coordinates.

The runner must use existing EIMS functions, rather than reimplementing the Analyzer:
- source_classify.classify_source / parser.parse_event_metadata
- evidence.build_evidence_records / incident_extract.incident_from_records
- bundle.summarize_file_evidence / correlate_bundle / build_evidence_items
- vendor_knowledge.vendor_reference_results / relevant offline summary functions

The CLI runner must explicitly record which code path executed and which stages were unavailable. Avoid HTTP routes as the default benchmark path because they commit History and may write vector knowledge. Provide an isolated integration test for HTTP flows later if needed.

## Modes and comparability

M0 = deterministic parser, incident extraction and rules without external web, RAG or generative AI.
M1 = M0 plus deterministic, locally curated vendor KB with applicability gates.
M2 = M1 plus local RAG only when real isolated embeddings/index are available and index contains no held-out material.
M3 = M2 plus optional LLM, only when explicitly enabled with a configured key and documented model/version; mark external/non-deterministic and record repeat runs.

Do not invent ablations: if a stage cannot be bypassed safely in current code, document actual executed path; mark NOT_RUN for unsupported modes. Compare modes on identical eligible cases with identical scorer, but report stage-specific metrics only for modes that emit them. Search fallback and LLM may require special treatment; prohibit hidden network calls in M0/M1.

## Metrics and denominator discipline

- Source family accuracy = exact matches / all annotated cases; include unknown as a class; show confusion matrix.
- Diagnostic identity macro/micro F1 and per-class support; unknown/no diagnosis is a class; do not count abstentions as silent exclusions.
- Finding span precision/recall/F1: match file name and annotated line/span under a written exact/overlap rule. Score first and terminal failure separately.
- Evidence citation precision = supported, exact file-line references / all emitted citation references; report citation coverage too, so returning no citations cannot look perfect.
- Correlation pairwise P/R/F1 over labeled unordered file pairs; weak association is not proven causal; also report false merge and false split.
- KB relevance precision = applicable, prerequisite-satisfied official KB IDs / all KB IDs emitted; separately report recommendation coverage. No recommendations => undefined precision, coverage 0 where relevant.
- Unsupported claim rate = unsupported material factual claims / all evaluated material factual claims, based on blinded manual review. Automated keyword proxies are not a defensible hallucination metric.
- Appropriate abstention precision/recall and false-certain diagnosis rate on unknown/insufficient-evidence cases.
- Latency: monotonic per-case wall-clock, 3 warmups if feasible, raw repetitions and p50/p95; record OS/CPU/Python/model/cache settings.

Undefined denominators must be represented as null/N/A with stated support, never as 100% or 0% by default. Show numerator and denominator for every metric, and breakdown by vendor, split and evaluation mode. Do not overinterpret percentage changes on a small corpus.

## Required artifacts

- gold/manifest.v1.json and case input files; annotation review log
- tools/eval_analyzer.py (or an existing reusable harness if discovered)
- tests for scorer and runner (fixture hash, false positive, empty denominator, no network, no DB writes, split leakage)
- results/<run-id>/config.json, predictions.jsonl, case_scores.jsonl, metrics.json, errors.csv and command/environment metadata
- docs/ANALYZER_BASELINE_RESULTS.md with only observed numeric results, sample size, confidence/uncertainty and limitations

## Release gate

A passing regression suite is not an accuracy score. No experimental performance claim until input hashes validated, gold labels reviewed, held-out split populated, mode verified, and an actual run produces the report. Do not modify operational databases or physical USBs during this phase.

## Implemented v1 adapter — 2026-10-25

See [execution and scoring policy](README.md). The manifest's first declared
file is the source/identity target. Mode names are `rule_only` (M0) and
`rule_kb` (M1); they differ only by actual per-file curated reference retrieval,
not by a hidden synthesis path. M2/M3 remain NOT_RUN. Stage evaluation does not
claim full summary-path ablation.

The initial AI-authored corpus is 17 DRAFT cases: 12 dev, 5 reserved heldout.
Human-reviewed support is zero until actual review is recorded. Draft dev smoke
metrics are stored separately and cannot satisfy the release gate above.
Heldout DRAFT execution is rejected. The versioned lock binds input hashes and
truth before execution; review metadata alone can subsequently be added.
Schema validation is followed by semantic file/span/pair, duplicate, scenario
and review-receipt checks. Machine checks cannot certify semantic independence.
