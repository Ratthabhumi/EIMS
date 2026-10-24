# Analyzer evaluation v1

The runner calls existing production parser, evidence extraction, incident
extraction, bundle and local vendor-reference functions. It does not call
`build_summary`, HTTP endpoints, History, SQL, vector writes, web search or
Gemini. This measures **stage outputs**, not the complete user-facing RCA.
M0 (`rule_only`) and M1 (`rule_kb`) share parser/extraction results; M1 executes
`vendor_reference_results` per file. Trace entries record actual invocations.
M2/RAG and M3/LLM are explicitly rejected as NOT_RUN. Installed packages do
not establish a usable model, isolated index, or actual model execution.

## Reproduce

Use the established project Python environment; install
`requirements-evaluation.txt` only if dependencies are missing. No model
download is required. Run from the Week 1 checkout:

```powershell
python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py -q
python tools/eval_analyzer.py --mode rule_only --split dev --include-draft --output evaluation/analyzer/results/new-m0-run
python tools/eval_analyzer.py --mode rule_kb --split dev --include-draft --output evaluation/analyzer/results/new-m1-run
```

Omit `--include-draft` for the reviewed-only cohort. With no human reviews,
the result is INSUFFICIENT_DATA, all reviewed metric denominators are zero,
and values are null. DRAFT numerical outputs appear only under
`exploratory_draft_only`; they are not scientific accuracy certification.
Heldout DRAFT execution is rejected even with `--include-draft`.

Inputs are UTF-8 synthetic text, exact-byte hashed (including line endings).
All paths must stay within the corpus; output is restricted to the checkout's
evaluation results or test-results directories. Outputs are create-once,
never overwritten or cleaned up automatically. Source SHA, Analyzer tree,
manifest SHA, runner/scorer SHA, dependency versions, seed setting, actual
trace, raw `perf_counter` timing samples and case exceptions are recorded.
Warmups default to 3 per case; measurements default to 3. Percentiles use
linear interpolation on warm samples, excluding import/cold-start latency.
Repeat comparisons require identical prediction hashes, not identical times.
Case errors count as incorrect outcomes rather than disappearing from metrics.

## Annotation and review

See [GOLD_PROTOCOL.md](GOLD_PROTOCOL.md), [review queue](gold/REVIEW_QUEUE.md)
and [manifest](gold/manifest.v1.json). Version 1 has 17 AI-authored synthetic
proposals, 12 dev and 5 reserved heldout; **zero human-reviewed cases** at
creation. No data is claimed as authorized field evidence. The review queue
is the initial proposal snapshot; the manifest and review-bound digest are
the authoritative current review state. Human labels must be reviewed against
inputs and official references, not adjusted merely to agree with predictions.

After an actual human reviews a case's complete label record, the operator may
record a public-safe reviewer alias with:

```powershell
python tools/review_analyzer_case.py --case-id win_policy --reviewer-id human-reviewer --confirm-human-review
```

This command records a human-review assertion; it does not authenticate a
human or prove independence. AI agents must never run it to create review
status themselves. Its receipt binds source files, truth, scenario and split.
Changing them invalidates the receipt. The heldout lock binds annotation and
input hashes separately from review status; it is a versioned integrity record,
not cryptographic access control. Changing heldout truth requires a new version
and disclosure, never silently replacing the lock after seeing results.
Exact/normalized hashes and scenario separation detect some leakage, not all
semantic resemblance. No human independent-validation claim is made.

Human claim/citation judgments use [manual_reviews.template.json](manual_reviews.template.json)
and [its schema](manual_reviews.schema.json). Bind every item to a case ID,
prediction hash, public-safe reviewer ID, exact emitted text and rationale;
citations also require file/line. `supported: null` records uncertainty rather
than forcing a binary answer. Pass `--manual-reviews path/to/reviews.json` on a
reproducible rerun. Stale hashes, missing text and duplicated judgments fail.
Metrics cover the reviewed subset only, with explicit support; they do not
claim exhaustive narrative review. No keyword-based hallucination score exists.

## Scoring boundaries

- The first file listed in each manifest case is the source/diagnostic target.
  Per-file metadata is preserved; bundles are not assigned an invented vendor.
- Identity uses parser `diagnosticCode`, or Windows/Fortinet/Cisco event ID
  when available. It does not imply failure, root cause or causal confidence.
- First/terminal exact references are recovered by matching returned incident
  text to original records. Repeated identical text produces multiple candidates
  and fails an exact single-span label, rather than guessing provenance.
- Evidence spans use exact file/line-set matches; citation counts retain
  duplicates. A correct coordinate is not semantic support. Windows severity
  headers and technical CTK status lines need human adjudication.
- Correlation calls the existing function separately for each unordered pair.
  STRONG/MEDIUM mean association, WEAK remains unproven; no causality is inferred.
- KB precision matches exact official URLs against reviewed applicability
  labels. Empty DRAFT KB lists are **unreviewed proposals**; observed 0/2 URL
  matches must not be presented as proof of irrelevant recommendations.
  Prerequisites and cross-vendor contamination remain NOT_MEASURED without
  separate human review. M0 KB denominators are zero because it does not execute
  retrieval, rather than because it has perfect recommendations.
- Macro metrics average truth-supported classes with defined denominators;
  undefined classes are explicitly listed. Micro uses single-label counts.
- Unsupported claims, semantic citation support, and root-cause abstention
  remain unmeasured without human judgments. `identity_abstention` only means
  no diagnostic identity emitted. It is not a narrative/RCA uncertainty metric.

No company logs, operational databases, physical USBs, private backups or
authentication settings are needed. Production Analyzer behavior is unchanged.
