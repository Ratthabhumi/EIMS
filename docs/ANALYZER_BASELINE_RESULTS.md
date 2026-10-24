# Analyzer Week 1 executed evaluation — 2026-10-25

**Scientific readiness: INCOMPLETE / INSUFFICIENT_DATA.** The evaluator works
and has emitted actual reproducible predictions. Human-reviewed gold support
is zero. All numerical results below are explicitly exploratory DRAFT-label
agreement, not validated accuracy or independent generalization evidence.

## Source, modes and artifacts

Original main: `bf634d9ddf86f44220ef961cf4be32988cfc5ee5`.
Week 1 preparation: `5655e3692434e1f93bea7d6cd9ef8b37885f48b1`.
Executed evaluator snapshot: `1612bbe3216fd36d01d4dbbb1c0566dcafed9955` on
`work/analyzer-week1-evaluation-2026-10-25`.
The subsequent artifact/report commit stores these runs without changing
Analyzer production behavior. Each run records its exact source/config hashes.
`git_dirty` may include newly generated result files; it does not imply an
unrecorded Analyzer change. No Analyzer source diff exists against original main.

- [M0 predictions](../evaluation/analyzer/results/20261025-v1-m0-dev-draft/predictions.jsonl),
  [metrics](../evaluation/analyzer/results/20261025-v1-m0-dev-draft/metrics.json),
  [environment/config](../evaluation/analyzer/results/20261025-v1-m0-dev-draft/config.json).
- [M1 predictions](../evaluation/analyzer/results/20261025-v1-m1-dev-draft/predictions.jsonl),
  [metrics](../evaluation/analyzer/results/20261025-v1-m1-dev-draft/metrics.json),
  [environment/config](../evaluation/analyzer/results/20261025-v1-m1-dev-draft/config.json).
- [Reviewed-only metrics](../evaluation/analyzer/results/20261025-v1-reviewed-dev/metrics.json):
  executed with default reviewed-only selection; zero eligible cases, null
  metrics and no fabricated predictions.

Each folder also contains case_scores.jsonl, errors.csv, manual_reviews.json,
raw timing samples and actual stage traces. Case errors: **0/12** per draft
mode. The empty reviewed run is not called a successful accuracy experiment.
Initial pre-commit prototype runs and a separate-process repeat are retained
locally under ignored result/test paths, without destructive cleanup. Versioned
v1 runs above are the reproducible publication artifacts.

M0 calls existing parser, file/evidence normalization, incident extraction,
evidence items and pairwise bundle correlation. M1 adds actual per-file local
vendor-reference retrieval. No build_summary synthesis, HTTP, SQL/History,
vector operations, web, RAG or Gemini executes. M2 and M3: **NOT_RUN**.

## Corpus and review status

All cases are newly authored safe synthetic proposals; none is a customer log
or an imported regression fixture. The AI author knew the existing pipeline,
so these are not independent human gold or blind test data. Source resemblance
checks and group locks reduce leakage but cannot prove semantic independence.

| Primary family | DEV DRAFT | Reserved HELDOUT DRAFT | REVIEWED |
|---|---:|---:|---:|
| Windows | 2 | 1 | 0 |
| Veeam | 4 | 1 | 0 |
| VMware | 2 | 1 | 0 |
| Fortinet | 2 | 1 | 0 |
| Unknown/noise | 1 | 1 | 0 |
| JSON | 1 | 0 | 0 |
| Total | **12** | **5** | **0** |

17 cases use 19 text files. The two dev bundles have one labeled positive and
one labeled negative unordered file pair. Heldout inputs/truth are locked;
**heldout execution count is 0**. A target of 40–60 has not been achieved and
was not filled with manufactured claims of review. Human review must cover
source, identity, first/terminal evidence, KB and uncertainty, not just filenames.

## Actual metric results and denominator boundaries

The reviewed baseline is **NOT_MEASURED** for every correctness metric: zero
reviewed cases (0/0 => null). Draft agreement below exists solely to test the
measurement pipeline and identify candidates for human adjudication.

| Metric | Reviewed | M0 DEV DRAFT | M1 DEV DRAFT |
|---|---|---|---|
| Source exact accuracy | null (0/0) | 12/12 | 12/12 |
| Diagnostic identity exact accuracy | null (0/0) | 12/12 | 12/12 |
| Source macro P/R/F1 | null (0 supported classes) | 6/6 class means, each 1.0 | same |
| Diagnostic micro F1 | null (0/0) | 24/24 = 1.0 | same |
| First failure exact file/line | null (0/0) | 11/12 | 11/12 |
| Terminal outcome exact file/line | null (0/0) | 10/12 | 10/12 |
| Evidence span precision | null (0/0) | 3/5 = .60 | 3/5 = .60 |
| Evidence span recall | null (0/0) | 3/4 = .75 | 3/4 = .75 |
| Evidence span F1 | null (0/0) | 6/9 = .667 | 6/9 = .667 |
| Citation coordinates mechanically valid | null (0/0) | 5/5 | 5/5 |
| Citation exact truth-line agreement | null (0/0) | 3/5 | 3/5 |
| Semantic support precision | NOT_MEASURED | 0 human labels; null | 0 human labels; null |
| Citation coverage | null (0/0) | 3/3 truth-positive cases | same |
| False-positive finding rate | null (0/0) | 1/9 truth-negative cases | same |
| Correlation P / R / F1 | null (0/0) | 1/1; 1/1; 2/2 | same |
| False merges / false splits | 0 pairs evaluated | 0 / 0 on only 2 labeled pairs | same |
| KB URL applicability agreement | NOT_MEASURED | NOT_RUN stage, null (0/0) | 0/2 against unreviewed empty proposals; **annotation gap**, not confirmed irrelevance |
| KB prerequisite satisfaction / contamination | NOT_MEASURED | NOT_MEASURED | NOT_MEASURED |
| Identity abstention P / R | null (0/0) | 6/6; 6/6 | same |
| False-certain identity rate | null (0/0) | 0/6 | same |
| RCA/narrative abstention | NOT_MEASURED | summary not executed | summary not executed |
| Unsupported material claim rate | NOT_MEASURED | 0 human-reviewed claims; null | same |

Source confusion matrix on DRAFT dev labels is diagonal: Windows 2, Veeam 4,
VMware 2, Fortinet 2, unknown 1, JSON 1; off-diagonal count 0. Full confusion
matrices and per-class precision/recall/F1/support, including UNKNOWN and
vendor diagnostic errors, are in metrics.json. Identity agreement does not
establish root cause. Empty denominator values remain null, never 100% or 0%.

## Runtime measurements and repeatability

Python 3.14.3 on Windows AMD64, existing project environment. `PYTHONHASHSEED=0`;
3 warmups and 3 measurements per case, 36 timing samples per nonempty mode.
Monotonic perf_counter wall time; linear-interpolated warm-sample percentiles:

| Executed path | p50 | p95 | Samples |
|---|---:|---:|---:|
| M0 stage-only | 0.4152 ms | 0.6479 ms | 36 |
| M1 stage-only + local references | 0.4629 ms | 0.7178 ms | 36 |
| Reviewed-only run | NOT_MEASURED | NOT_MEASURED | 0 |

These small text inputs and warm in-process functions exclude cold import,
HTTP, DB, full summaries, embeddings and LLM latency. They are not dashboard
or complete incident-investigation performance claims. Separate-process M0
rerun reproduced prediction hashes **12/12**; timing equality was not required.
M0 and M1 intentionally share all classification/extraction outputs; M1's
reference trace really executes. No invented AI-ablation comparison is made.

## Failure candidates, ranking and implementation decision

| Priority | Case / exact source evidence | Actual observed output | Interpretation / next action |
|---|---|---|---|
| 1 | fort_config input.txt:1, informational configuration update with error-log-retention setting | Selected as first/terminal signal and citation | Potential false positive from generic error token; review structured context before narrow suppression |
| 2 | esxi_tracker input.txt:2, CTK_CTKUNLINK result:2620 | Terminal stayed at line 1 and line 2 not cited | Candidate missed technical signal; verify code semantics before extending failure vocabulary |
| 3 | win_policy input.txt:4, Level: Error | Cited alongside actual description at line 5 | Coordinate is real; whether header supports a material claim needs human judgment |

No Analyzer business-rule fix was made from unreviewed labels. The original
inputs/predictions remain preserved. This prevents changing rules or truth after
seeing outcomes merely to improve a score. New tests concern evaluator integrity;
they do not claim to resolve these three diagnostic candidates. Once adjudicated,
preserve confirmed failures as dev regressions, make the smallest source fix,
rerun dev with unchanged scoring policy and leave heldout separate.

## Tests, blockers and next step

Before changes: `python -m pytest tests/test_analyzer_reliability.py -q -o addopts=`
=> 129 passed / 0 failed / 0 skipped / 0 errors; 3 existing warnings.

After implementation:
`python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py -q -o addopts=`
=> 160 passed / 0 failed / 1 skipped / 0 errors; 2 dependency warnings on the
latest local run. Skip: Windows symlink creation refused. The initial docstring
escape warning is still existing source debt, not fixed by import caching.
CI evidence is reported separately on the final PR head.

Reproduction commands and exact scoring policy:
[evaluation README](../evaluation/analyzer/README.md).
Human review packet: [review queue](../evaluation/analyzer/gold/REVIEW_QUEUE.md).

Remaining Week 1 blockers: zero human-reviewed gold; small/nonrepresentative
synthetic corpus; heldout never evaluated; no blinded claim/citation support
audit; no KB prerequisite review. Full summary-path evaluation, production
accuracy and M2/M3 comparisons remain outside demonstrated evidence.

Week 2 first action: adjudicate the 12 dev proposals (including the three
mismatch candidates and two emitted KB references), record actual reviewer
receipts, freeze a scientifically defensible reviewed corpus, then rerun the
reviewed-only baseline. Do not tune on or execute the five heldout proposals
before their independent review. Expand toward 40–60 only after validating
annotation quality; frontend/USB/model expansion is not the priority.
