# File access / possible copying: feasibility only

No exfiltration detector is implemented or claimed. A Windows object-access event is evidence of an audited access action, not proof that a file was copied to a particular destination or leaked.

Before evaluation: confirm relevant Windows audit policy, object SACL coverage, Security-log retention and privileges; identify permitted process/user/object/access fields and reliable clocks. Correlate with approved EDR, removable storage, share access, network or DLP evidence where available. The existing USB collector's System/Application scope does not imply Security-channel evidence exists.

Expected study output: supported evidence types, minimum audit prerequisites, permitted sanitized fixtures, negative controls (legitimate reads/backup/indexing), and an engineer-reviewed interpretation rubric. Do not collect sensitive file paths or user identities without approval. Audit settings must not be changed as part of this task.

Primary source checked: [Microsoft event 4663](https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4663). Full audit-policy and destination-corroboration research is delegated via RESEARCH_HANDOFF_FOR_CHATGPT.md; these prerequisites have not been tested on a target machine.
