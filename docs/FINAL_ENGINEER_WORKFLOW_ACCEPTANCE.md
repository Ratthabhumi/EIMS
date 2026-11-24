# EIMS — Engineer Workflow Acceptance (truthful status)

**Date:** 2026-11-19 · HEAD `85493b2` · **No end-to-end run this round** (no disposable database).

Legend: **Y** implemented and supported by source + tests · **P** partial · **N** not available.

## 1. The ten questions

| # | Engineer question | Current support | Evidence | Gap |
|---|---|---|---|---|
| 1 | What happened? | **Y** | analyzer produces findings from normalized events | — |
| 2 | When? | **Y** | `event_time` / `occurrence_time`, UTC-normalised | — |
| 3 | Which asset/host? | **P** | resolved asset id where identity is verified; unresolved stays NULL | unresolved evidence cannot name a host (by design) |
| 4 | What evidence supports it? | **Y** | incident evidence rows reference source ids + digest | no raw-payload retention |
| 5 | Why does EIMS believe it? | **P** | correlation reasons persisted (strong/medium/weak) | no per-rule explanation surfaced |
| 6 | Confirmed vs inferred? | **P** | confidence + reasons stored | not consistently shown in UI |
| 7 | What to inspect next? | **P** | AI/analysis suggestions exist | not tied to evidence ids |
| 8 | How to remediate? | **P** | remediation text in knowledge/analysis | no structured action record |
| 9 | Risks of remediation? | **N** | — | not modelled |
| 10 | What proves resolution? | **N** | status can be set to resolved | **no verification evidence requirement** |

## 2. Data sufficiency matrix

| Need | Existing model/API | Status |
|---|---|---|
| Stable source event identity | `source_event_key`, `UNIQUE(source_type, source_id)` | Y |
| Timestamps + timezone | tz-aware columns, UTC coercion | Y |
| Asset identity | `asset_id` FK, nullable, never inferred | Y |
| Raw evidence provenance | reference ids + digest (no payload copy) | P |
| Parser name/version | parse metadata on winlog rows | P |
| Finding ↔ event linkage | evidence binding | Y |
| Incident lifecycle | open→triage→investigating→resolved→closed | Y |
| Investigation notes | audit log entries | P |
| Remediation action + actor | free text / knowledge entries | P |
| Verification result + time | **absent** | **N** |
| Reprocessing/idempotency | dedupe key + unique evidence | Y |

## 3. Resolution integrity

Current: an incident can be moved to `resolved` without any recorded verification
evidence (closing requires a Knowledge Reviewer, resolving does not).

**This is the remaining product-path defect.** The minimum remediation is a verification
record (what was checked, evidence reference, who, when, pass/fail) and a rule that
`resolved` cannot be set without one. That is a schema + API change and was **not**
implemented in this round; it is recorded as the next product task.

## 4. What this document does not claim

It does not claim the workflow is behaviourally verified end to end. The stages listed as
**P/N** are source-inspected only, and the verification stage is absent.
