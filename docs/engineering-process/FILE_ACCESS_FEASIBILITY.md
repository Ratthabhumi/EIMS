# File access / possible copying: feasibility only

No exfiltration detector is implemented or claimed. A Windows object-access event is evidence of an audited access action, not proof that a file was copied to a particular destination or leaked.

| Question | Required evidence | Can conclude | Cannot conclude | Limitations |
|---|---|---|---|---|
| Was access requested? | Provider-qualified 4656, audit policy and matching object SACL | A handle/access request was audited | Successful copy or destination | Requested rights differ from exercised rights |
| Were rights used? | 4663 with account, process, object and access mask | Audited object access-right use | File contents were exported | Coverage, retention and clock quality must be checked |
| Was an object deleted? | 4660 plus related handle/object records | Audited deletion | A copy was made first | Object name may need related records |
| Was a share accessed? | 5140/5145, share policy and corresponding audit configuration | Share access or access-check evidence, according to event semantics | Successful content transfer or malicious intent | Not a packet capture or content transcript |
| Was data sent elsewhere? | Permitted process/EDR, destination/network/DLP evidence and a defensible timeline | Only the transfer facts that corroborating evidence actually supports | Exfiltration from file access alone | Missing audit events do not establish absence of copying |

Source: [Microsoft Audit File System](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/audit-file-system). This source documents matching SACL/audit requirements; share and destination-specific implementation remains a feasibility item, not a new parser capability.

Before evaluation: confirm relevant Windows audit policy, object SACL coverage, Security-log retention and privileges; identify permitted process/user/object/access fields and reliable clocks. Correlate with approved EDR, removable storage, share access, network or DLP evidence where available. The existing USB collector's System/Application scope does not imply Security-channel evidence exists.

Expected study output: supported evidence types, minimum audit prerequisites, permitted sanitized fixtures, negative controls (legitimate reads/backup/indexing), and an engineer-reviewed interpretation rubric. Do not collect sensitive file paths or user identities without approval. Audit settings must not be changed as part of this task.

Primary source checked: [Microsoft event 4663](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4663). Full audit-policy and destination-corroboration research is delegated via RESEARCH_HANDOFF_FOR_CHATGPT.md; these prerequisites have not been tested on a target machine.
