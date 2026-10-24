# EIMS Analyzer — Week 1 verified source audit and research gap

Date: 2026-10-25 (Asia/Bangkok)
Baseline target: main at bf634d9ddf86f44220ef961cf4be32988cfc5ee5.
Scope: read-only inspection of GitHub sources and current official product documentation. No runtime benchmark was executed at the time of this audit.

## Existing source verified (reuse, do not rebuild)

- backend/domain/analyzer/services/source_classify.py: source-family classifier; unknown_text fallback; weak filename hints.
- backend/domain/analyzer/services/parser.py and vendor_parsers.py: Windows, Veeam, VMware, Fortinet, Cisco ASA, Linux syslog and structured JSON handling, with coverage varying by format.
- backend/domain/analyzer/services/evidence.py and incident_extract.py: normalized evidence records, chronology, first/terminal signals, uncertainties.
- backend/domain/analyzer/services/bundle.py: bounded uploads, sha256, exact file/line evidence, conservative strong/medium/weak/none correlation.
- backend/domain/analyzer/services/vendor_knowledge.py and summary.py: deterministic official KB gates, optional live search/RAG/Gemini paths.
- backend/api/routers/analyzer/analyze.py: single-file and multi-file endpoint, History persistence, optional vector export.
- tests/test_analyzer_reliability.py: substantial existing synthetic regression suite including test_golden_veeam_acceptance_semantics; not an independent held-out evaluation.
- docs/BENCHMARK_RESULTS.md: Sprint 11 search/timeline latency only; NOT Analyzer diagnostic accuracy.

## Research-to-implementation gap matrix

| Product / official reference | Principle | Existing EIMS mechanism | Still unproven or gap | Week 1 measurement |
|---|---|---|---|---|
| Splunk ES: https://help.splunk.com/en/splunk-enterprise-security-8/administer/8.5/investigations/findings-and-finding-groups-in-splunk-enterprise-security | Findings linked to contributing events and investigation | Structured incident, evidence items, Analysis History | How many cited lines genuinely support findings? | Exact provenance/support precision |
| Elastic: https://www.elastic.co/docs/solutions/observability/logs/categorize-log-entries | Log categorization and reduction of repetitive/noisy events | Classifier, compaction, failure-signal suppression | Robustness to benign lines, filename decoys, long noisy records | Source confusion matrix and false positives |
| Wazuh: https://documentation.wazuh.com/current/user-manual/ruleset/testing.html | Reproducible decoder/rule testing against sample inputs | Deterministic vendor parsers and regression tests | Independently annotated incident set and measured classification/finding quality | Gold dataset + executable scoring |
| Grafana Loki: https://grafana.com/docs/loki/latest/ | Low-cardinality labels vs high-cardinality structured metadata | Source/vendor fields and operation/session correlation | False merges/splits across files and clock domains | Pairwise correlation P/R/F1; abstention |
| Veeam/VMware vendor troubleshooting | Exact diagnostic signatures, applicability conditions, uncertainty | Vendor-specific codes and official KB gating | Does article match actual evidence, not merely vendor/product? | KB applicability precision; unsupported-claim rate |

This is a design comparison, not a claimed head-to-head accuracy benchmark against those products.

## Highest priority experimental gaps

1. No verified independent held-out gold corpus and frozen annotation policy was established in the inspected source.
2. No source-backed Analyzer diagnostic accuracy, extraction F1, citation precision, correlation F1, KB relevance, abstention metrics or latency distribution was found in the existing BENCHMARK_RESULTS document.
3. Rule-only, rules+curated KB, local RAG, and optional LLM modes are not yet demonstrated under a common isolated, deterministic evaluation harness. Presence of optional code does not prove availability.
4. The HTTP analyzer path persists History and optionally updates vector knowledge; evaluation must not write to operational DB or allow case-to-case retrieval contamination.
5. Existing regression fixtures must be marked as development fixtures; copied/transformed versions cannot constitute independent held-out evidence.

## Week 1 completion criteria

- Snapshot exact commit, runtime environment, dependency versions, random seeds and experiment configuration.
- Preserve existing regression tests and record fresh pass/fail counts; do not copy prior claimed counts.
- Create 40–60 safe, independently labeled cases if realistic: Windows, Veeam, VMware, Fortinet, negative/unknown, plus supported Cisco/Linux/JSON as appropriate.
- Separate dev and held-out by incident scenario/family, not merely by duplicate file or line.
- Require expert annotation of source family, diagnostic identity or explicitly unknown, failure spans, first/terminal outcome, correlation pairs, applicable official KB references, abstention.
- Implement import-safe CLI runner and metric scorer reusing existing parser/evidence/bundle/vendor KB code, with explicit modes.
- Evaluate and store per-case predictions, confusion matrix, metric numerator/denominator, zero-denominator policies, timing raw samples and p50/p95 in versioned machine-readable files.
- Commit only synthetic or demonstrably authorized sanitized data; never actual credentials or customer identifiers.
- Block 'PASS' or accuracy claims if held-out corpus is empty, tests did not execute, annotations are not reviewed, or optional services failed to run.

## Operational constraints

No USB D:/E: writes. No production/dev DB resets or data mutation. No new SIEM stack. No arbitrary network/LLM calls during deterministic offline baseline. Limit changes to evaluation-related paths until a measured error justifies a targeted Analyzer fix.

## Status at audit

Source audit: VERIFIED.
Independent gold corpus: NOT VERIFIED / TO BUILD.
Fresh test run: NOT RUN (remote source inspection only).
Analyzer baseline metrics: NOT MEASURED.
USB source parity: NOT CHECKED (physical drives unavailable here).

## Local execution continuation — 2026-10-25

The remote-only snapshot above is historical. Actual implementation and fresh
test results are recorded in [current state](ANALYZER_CURRENT_STATE_2026.md)
and [baseline results](../ANALYZER_BASELINE_RESULTS.md). The initial empty
manifest has been extended rather than recreated. No Analyzer production
behavior was changed before or after the initial dev smoke measurement.

| Research source | Principle | Current implementation | Measured gap | Proposed improvement | Validation | Actual result |
|---|---|---|---|---|---|---|
| [Splunk findings](https://help.splunk.com/en/splunk-enterprise-security-8/administer/8.5/investigations/findings-and-finding-groups-in-splunk-enterprise-security) | Link findings to contributing evidence | Evidence items + incident sketch | Coordinates alone do not establish semantic support | Human support labels bound to prediction hashes | Separate coordinate/semantic metrics | Coordinate outputs measured; semantic review count 0 |
| [Elastic categorization](https://www.elastic.co/docs/solutions/observability/logs/categorize-log-entries) | Categorize similar messages and noise | Source classifier + signal suppression | Dev proposals expose config/header mismatch | Review false-positive candidates before rule changes | Negative cases with exact spans | 3 dev cases need adjudication; no commercial comparison |
| [Wazuh rule testing](https://documentation.wazuh.com/current/user-manual/ruleset/testing.html) | Repeatable sample-based decoder/rule checks | Existing parser + 129 regression tests | Regression success is not accuracy | Separate corpus/runner/scorer | Hash-validated, scenario-separated dev run | Executed 12 DRAFT cases; 0 reviewed, no certified accuracy |
| [Loki structured metadata](https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/) | Distinguish metadata from indexed labels | Existing job/resource identity correlation | Two-pair sample cannot establish generalization | Expand reviewed positive/negative pairs | Pairwise existing correlate_bundle invocations | 1 TP, 0 FP, 0 FN on 2 DRAFT-labeled pairs |
| [Microsoft 1129 guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/netlogon-event-id-5719-or-group-policy-event-1129) | Interpret event within connectivity context | Windows metadata parser | Severity header may not support a material diagnosis | Human adjudication of evidence, not coordinate-only PASS | Source/identity and span scores kept separate | Identity matched; evidence-header candidate remains unreviewed |
| [Veeam CBT guidance](https://www.veeam.com/kb1113) | CBT troubleshooting is conditional, not universal | Existing CBT diagnostic + local article gates | Signature recognition does not establish repair applicability | Review prerequisites before recommending actions | M1 records emitted official URLs | References execute; prerequisite score NOT_MEASURED |
| [Broadcom snapshot article](https://knowledge.broadcom.com/external/article/424591) | Snapshot failure context and version applicability matter | Vendor KB operation-local gates | Keyword agreement alone is not applicability | Human KB label review; preserve per-file context | M1 per-file trace plus exact URL labels | Reserved snapshot case not executed; real environment compatibility unverified |
| [Fortinet log ID reference](https://docs.fortinet.com/document/fortigate/7.2.3/fortios-log-message-reference/34314/log-id-numbers) | Stable IDs and structured event context | Fortinet key/value parser | Benign configuration message selected as signal in DRAFT dev | Review configuration-event suppression candidate | Preserve exact raw input and prediction | Direct reference fetch returned 403; documentation access limitation disclosed |

Official references were accessed on 2026-10-25; Fortinet's direct page could
not be fetched. No vendor log samples were copied into the corpus. These are
engineering analogies and annotation aids, not comparative accuracy results.
In particular, Veeam CBT reset guidance is not authority to perform a reset or
proof it is appropriate for any synthetic/field incident.
