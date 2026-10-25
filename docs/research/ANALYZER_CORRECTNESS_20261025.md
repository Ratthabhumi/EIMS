# Evidence correctness repairs — 2026-10-25

Base: `1c6d3e1e65b6d64adabc3601bfc96b350406f30f`. This production-behavior
change is isolated from evaluation infrastructure and has not been merged into
main. No Gold label or review receipt is changed. These are reproduced software
contract defects supported by source, executable tests and vendor semantics,
not attempts to fit unreviewed DRAFT scores.

## Reproductions, corrections and limits

| Problem / source evidence | Before | Small correction | Regression / remaining limit |
|---|---|---|---|
| get_curated_summary returns the shared registry object; routes attach evidence, steps and nested incidents | Two requests returned the same object; a synthetic case-A evidence marker appeared in case B | Return a deep model copy for each request, preserving the template | Nested incident/list isolation; mapped event behavior preserved. Does not establish causal accuracy |
| Unknown Veeam/VMware fallback unconditionally says task/session completed Failed | Benign/unknown records receive an unsupported final outcome | Only explicit VEEAM-SESSION-FAILED identity gets that wording; unknown identities state final outcome unknown | Negative unknown cases and positive explicit Failed control. Possible-cause lists are not proven causes |
| CTK_CTKUNLINK result:2620 is absent from canonical failure signals/evidence filter | No finding/citation for the technical error record | Match CTK operation namespace plus exact result 2620, share pattern with evidence builder | Negative result 0/26200/unrelated number controls. Last technical failure is not an explicit final job status |
| Structured Fortinet successful config edit contains error-log-retention setting | Generic token promoted the record to incident/citation | Suppress only recognized config IDs, event/system, information, edit, affirmative configuration-success message with no contradictory failure tokens | Genuine error level, failed update and contradictory severity remain visible. Other formats remain unproven |

Windows Level: Error remains severity evidence, not evidence for DNS/NIC or
another physical cause. It is not globally deleted to improve a DRAFT score;
the parallel v2 annotation/claim-role work distinguishes severity from failure
description and causal support. That semantic adjudication remains pending.

## Vendor/source authority

- [Broadcom technical article 442155](https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html)
  identifies 2620 as DISKLIBERR_CHANGETRACK / CTK_CTKUNLINK. Its vSAN-specific
  physical cause, environment and fix are **not** inferred for these generic
  synthetic ESXi records, and no new KB repair applicability is granted.
- [Fortinet staff technical tip](https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472)
  documents the configuration-change identities and structured informational
  records. Suppression is deliberately narrower than all configuration events.
- [Microsoft troubleshooting guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance)
  distinguishes event details and probable causes; event identity/severity
  alone is not proof of a particular root cause.

## Executed red/green evidence

The first new-test run exposed a missing test import as well as product failures;
the import was corrected before establishing the product baseline. No harness
NameError is counted as an Analyzer defect.

Validated red command, before source edits:
`python -m pytest tests/test_analyzer_reliability.py -q -o addopts=`
=> **5 failed, 136 passed**, no skips/errors, 2 existing dependency warnings.
The five failing assertions represent the four defect groups above (two vendor
families exercise the unknown-outcome defect). XML is retained locally under
test-results/correctness-before-validated.xml.

Green command:
`python -m pytest tests/test_analyzer_reliability.py tests/test_analyzer_evaluation.py -q -o addopts=`
=> **172 passed, 1 skipped, 0 failed, 0 errors**, 2 existing dependency warnings.
Skip: Windows denied symlink creation. The original 129 regressions are intact;
12 new parametrized checks extend their file. The initial fresh-checkout invalid
docstring escape warning is existing source debt and was not repaired/suppressed.

Further combined full-investigation testing and exact-head CI are recorded in
the PR after evaluation infrastructure integration. Before/after DRAFT outputs
must remain separate; no human-reviewed accuracy or root-cause correctness is
certified by these software regressions.

## Controlled native investigation comparison

Before source `ddf717e81e389eb69cdb338becf0ba8d3bb6f3a7`; corrected source
`522e28607347d0703b007a1a2dde217847bd39fa` (contains fix cb97135 plus the
unchanged evaluator). All three modes preserve exact manifest/annotation,
scorer/runner, semantics, full-adapter and grounding hashes. Configuration files
declare untracked-artifact dirtiness. Subsequent merges add only the byte policy,
documentation and retained exploratory outputs; Analyzer/evaluator code is unchanged.

| Exploratory DEV comparison, 12 DRAFT | Before | After |
|---|---:|---:|
| Event identity agreement | 12/12 | 12/12 |
| Binary failure agreement (3 positive / 9 negative) | 12/12 | 12/12 |
| Failure-type proposal agreement | 11/12 | 11/12 |
| First observed failure agreement | 12/12 | 12/12 |
| Last observed failure agreement | 11/12 | 12/12 |
| Explicit terminal agreement (all null) | 12/12 | 12/12 |
| Positive explicit-terminal support | 0 | 0 |
| Full native citation coordinate overlap | 3 TP / 0 FP / 1 FN | 3 TP / 0 FP / 1 FN |
| Full emitted claims awaiting human judgment | 135 | 134 |

M0, M1 and full path all execute 12 DEV, zero HELDOUT, zero reviewed, zero
execution errors. Last-observed improvement reflects recognition of CTK 2620;
it is not validated accuracy. The v2 projection already excluded the narrow
successful Fortinet record, so no aggregate detection gain is claimed from that
production correction. Windows taxonomy remains UNCLASSIFIED versus the DRAFT
proposal; no unsupported rule change was made to force agreement. Native
single-file citations still do not include every proposed failure line: 3/4
coordinate recall remains a candidate for review rather than a claimed fix.

Explicit-terminal sensitivity, physical RCA correctness, narrative abstention
quality, semantic support and unsupported-claim rate remain undefined/unmeasured.
Typed UNKNOWN fields and matching coordinates do not prove narrative correctness.
M2/M3 remain NOT_RUN. No latency improvement is claimed from these small noisy
warm-harness timings, which exclude real HTTP/auth/PostgreSQL.

Combined executed regression: **189 passed, 1 skipped, 0 failures/errors**,
190 collected, 12.097 seconds in JUnit. The same Windows symlink privilege skip
applies. Independent-process corrected full prediction hashes match **12/12**;
the baseline independent repeat also matched 12/12. Synthetic two-file corrected
demo returns MEDIUM association, explicit FAILED, root UNKNOWN and an equal
isolated History roundtrip. This is not operational PostgreSQL persistence.

Artifacts: `evaluation/analyzer/results/20261025-controlled-after-{m0,m1,full}`
and `20261025-controlled-demo-after`. Prior controlled baseline and v1 outputs
remain unchanged. Actual CI status must be read on the final PR head; local
results are not a substitute for exact-head CI.

## Remaining work by priority

1. Human semantic adjudication when available: fort_config, esxi_tracker,
   win_policy; all 12 remain DRAFT with blank reviewer fields.
2. Assess remaining native citation coverage and Windows taxonomy against
   evidence, without tuning against an unreviewed target. Expand a separate
   positive-final-outcome benchmark only after annotation protocol agreement.
3. Claim-level human grounding before reporting unsupported-claim rates or RCA
   accuracy. See the hash-bound queue and Thai DEV packet in the base PR.
4. Production persisted-source viewer, real PostgreSQL/HTTP/auth integration,
   USB import and M2/M3 require their own scoped validation; none is certified.
   Bounded research questions are handed off in ANALYZER_RESEARCH_HANDOFF_20261025.md.

This is a dependent PR targeting the Week1 evaluation branch (PR #2), not main.
No main merge, demo checkout edit, operational database action, authentication
change, customer log export or external model execution was performed.
