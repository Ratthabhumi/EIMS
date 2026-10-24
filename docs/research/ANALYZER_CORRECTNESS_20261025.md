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
