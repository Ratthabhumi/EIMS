# FortiGate HA — evidence capture checklist (2026-11-22)

Applies to the two class D records that stay **TECHNICAL_UNVALIDATED**:
* `candidate:fortinet-fortios:ha:failover-reason-from-ha-status` (evaluator `evaluate_fortigate_ha_selection` exists; only authored strings were tested)
* `candidate:fortinet-fortios:ha:unexpected-failover-causes` (no evaluator)

No FortiGate or recorded real output is available in this environment, so **no output was written or simulated**. Technical status stays blocked until real output is supplied.

## Sources read for this checklist (already cited by the records)
* Fortinet Community, "Technical Tip: Understanding FortiGate HA failover causes from HA status output" — https://community.fortinet.com/t5/FortiGate/Technical-Tip-Understanding-FortiGate-HA-failover-causes-from-HA/ta-p/264123 (page date 2023-07-14; text says "Any supported version of FortiGate"; FortiOS 6.2 is not stated; uses "Primary selected using").
* FortiOS 6.2.0 Cookbook, "Check HA sync status" (older "Master selected using" wording).
* Fortinet Community, "Technical Tip: Troubleshooting unexpected High Availability (HA) failover" — https://community.fortinet.com/t5/FortiGate/Technical-Tip-Troubleshooting-unexpected-High-Availability-HA/ta-p/228854 (published 2022-11-08; no FortiOS version stated).
Version applicability of either article to FortiOS 6.2.x is **not established** by the text; 6.2.14 must not be claimed.

## Commands to capture (read-only)
| Command | What the cited article says it shows | Needed for |
|---|---|---|
| `get system ha status` | warnings, last HA events, sync status, heartbeat counters, primary/secondary, the "Primary selected using" lines with a timestamp | failover-reason evaluator (positive + negative) |
| `diagnose sys ha history read` | election history (up to 512 entries), link status changes | unexpected-failover record |
| `diagnose sys ha dump-by group` / `dump-by vcluster` | `linkfails`, `mondev` (1 = up, 0 = down), `state` (2 = primary, 3 = secondary), `link_failure`, `uptime/reset_cnt` | unexpected-failover record |
| `diagnose sys ha mac` | interface status on both members (1 = down, 0 = up) | unexpected-failover record |
| `get system status` | FortiOS version/build of the captured unit | version scope |

## Scenarios to capture (each from a real cluster, with the capture time and FortiOS build)
| # | Scenario | Expected line (as quoted by the article) | Polarity |
|---|---|---|---|
| 1 | Monitored interface down | `… selected as the primary because the value … of link-failure + pingsvr-failure is less than peer member` (6.2.0: `Master selected using … least value`) | positive |
| 2 | Peer member down | `… because it's the only member in the cluster` | positive |
| 3 | Override on, higher-priority unit rejoins | `… because its override priority is larger than peer member` | positive |
| 4 | Override off, larger uptime wins; also after an HA uptime reset | `… because its uptime is larger than peer member` | positive (not a fault) |
| 5 | High memory usage on the peer | `… because there is high memory usage on peer member` | positive |
| 6 | Manual `execute ha failover set` | `… because EXE_FAIL_OVER flag is set on peer member` | positive (not a fault) |
| 7 | Initial election | `… because its serialno is larger than peer member` | negative for "failover cause" |
| 8 | Healthy, no transition | no selection line indicating a change | negative |
| 9 | Unrecognised wording from another FortiOS release | any other string | negative (evaluator must not interpret) |

## Acceptance rules for the evidence
1. Output captured from a real unit (lab or authorised), redacted of serials/addresses, with `get system status` version/build and the capture timestamp.
2. Stored as run-bound evidence (`technical_evidence_fortigate_ha.json`), tied to the record content hash; each case lists the raw line, the evaluator result and the expected value taken from the article.
3. Authored or paraphrased strings never count; wording differences between FortiOS releases are recorded, not normalised silently.
4. For `unexpected-failover-causes`: build an evaluator only for deterministic fields (`state`, `mondev`, `linkfails`, `reset_cnt`) after real output shows their layout; until then it remains `evaluator_not_mapped`.
5. A network engineer must review the semantics (what counts as a fault) before any approval.

Blocker: real FortiGate HA output and a reviewer with Fortinet HA expertise.
