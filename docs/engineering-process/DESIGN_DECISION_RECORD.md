# Engineering decision record

| ID | Trigger / user need | Decision and rationale | Verification / trade-off |
|---|---|---|---|
| DD-01 | Preserve working demo and private files | Separate worktree from verified supervision baseline | Original checkout unchanged; no broad staging |
| DD-02 | Investigate rather than guess | Narrow deterministic evidence gates for Windows 1129/41 before optional synthesis | Regression-first; uncertain causes remain empty, not replaced by generic hardware/network guesses |
| DD-03 | Avoid cross-domain contamination | Scope incident unknowns to actual source/signatures | Non-VMware negative controls; no global CTK/VMDK fallback |
| DD-04 | Confidence clarity | Remove automatic medium fallback and clarify diagnostic versus association meaning in UI | Keep old API field for compatibility; legacy records may retain older conventions |
| DD-05 | Secure input without rewriting pipeline | Reuse bounded reads and safe name/type rules; reject invalid uploads before parsing/persistence | Auth remains existing demo/secure policy; content validation is layered, not perfect |
| DD-06 | Preserve real scope | Log investigation is evaluation core; USB endpoint import stays separate | As-built diagrams reflect distinct pipelines; broader modules retained |
| DD-07 | Evidence before improvement claims | Prepare task evaluation with blank outcomes and anonymized data | Real participants arranged by student; no simulated human results |
| DD-08 | Public credential exposure | Prepare environment-driven configuration; do not rotate or restart | Publication gate records unresolved owner action; history remains exposed |
| DD-09 | Missing evidence must remain missing | Display Not supplied for absent metadata; remove the fixed event count in UI/PDF | Browser regression with omitted metadata; retain original API data |

Alternatives rejected: wholesale architecture rewrite, deleting old modules, guessing exfiltration from access events, treating catalog entries as validated incidents, and publishing all local files. Revisit only with specific evidence and bounded acceptance criteria.
