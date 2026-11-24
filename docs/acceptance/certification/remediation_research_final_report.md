# Remediation research final report (2026-11-22, second pass)

Method: for each of the 16 ledger records marked `BLOCKED`, the cited official page was re-fetched on 2026-11-22 (`tools/research_remediation_sources.py` fetcher; pages cached outside the repository), searched for permission, rollback, post-action verification, healthy-state and impact statements, and only **verbatim** sentences were adopted. `tools/apply_remediation_fields.py` re-checks every quote against the live page before writing (dry run passed, then applied). Nothing was written from memory. Evidence stays `PENDING_HUMAN_REVIEW`; nothing here is a human review.

## Result
| | Records |
|---|---:|
| Researched | 16 |
| Gained at least one **stated**, source-quoted field | **7** |
| Searched, nothing further stated by the cited page (stay blocked) | **9** |
| Became eligible for diagnostic use | **0** |
Why 0: these records are class E (14, unmapped: no parser or evaluator exists) or class D (2, state/telemetry: no collector), so the adapter marks them INELIGIBLE or BLOCKED by design; vendor text cannot change that. What the research changes is how complete they are if a human later reviews them as reference knowledge. Eligibility artifact after regeneration: 911 records, 1 ELIGIBLE, 42 BLOCKED, 868 INELIGIBLE (unchanged). The ledger now reads 9 BLOCKED / 11 PARTIAL_EVIDENCE_ADDED_STILL_BLOCKED / 5 MANUAL_REVIEW_REQUIRED / 3 RESOLVED_RULE_DEFECT (28 records). Its `missing` column is the coarse KnowledgeEntry-contract view (rollback, post-action verification, healthy output); per-field state is in each record's `operational_fields`.

## Per-record evidence (STATED = verbatim quote from the official page; retrieval 2026-11-22)
| Record | Field | State | Evidence |
|---|---|---|---|
| fortinet-fortios:ha:split-brain-or-formation-failure | verification_steps | STATED | docs.fortinet.com FortiOS 6.2.0 Cookbook: "If everything seems to be in working order, run get system ha status to verify that HA has formed successfully." |
| | operational_impact | STATED | "The connections to the FortiGates in the cluster work intermittently when trying to connect with administrative access. Sessions cannot be established through the FortiGate, and the traffic drops." |
| | rollback, healthy-state output | NOT STATED | page searched; no rollback; expected output of `get system ha status` is not shown |
| microsoft-windows-failover-cluster:service:fails-to-start | rollback_steps | STATED | Microsoft Learn: "After you use this change for testing, return these settings to the original configuration." (applies to the temporary firewall change only) |
| | destructive_risk | STATED | "leave this change in place after you finish troubleshooting." (do not leave the firewall test change) |
| microsoft-windows-dhcp:client:cannot-obtain-lease | required_permission | STATED | "Run Wireshark as administrator on both the client and server." (capture step only) |
| | verification_steps | STATED | "If all are present, the DORA process is likely successful." |
| microsoft-hyper-v:management:console-connect-or-auth-failure | required_permission | STATED | "Ensure users are members of: Hyper-V Administrators Remote Management Users Storage Replica Administrators (if applicable)" |
| microsoft-hyper-v:vm:fails-to-migrate-start-or-inaccessible | rollback_steps | UNVERIFIED | page says to retain the VHDX and back up the .vmcx/.vmrs files, but gives no restore procedure; not counted as stated |
| veeam-vbr:health-check:capacity-tier-corrupted-chain | verification_steps | STATED | Veeam help center: "If Veeam Backup & Replication does not find any corrupted data, the health check completes successfully." |
| veeam-vbr:hotadd:stuck-vmdk-on-proxy | destructive_risk | STATED | KB1775: "Do not check the box to delete files from datastore!" |
| | verification_steps | STATED | "After the disk is released from the proxy, attempt Consolidation again." |
| fortinet-fortios:ha:failover-reason-from-ha-status, fortinet-fortios:ha:unexpected-failover-causes | all eight | NOT STATED / not found | community pages searched; no rollback, permission or verification wording beyond what the record already carries (the second page warns about uptime reset, already in the record) |
| microsoft-windows-dns:server:query-response-delay | all eight | NOT STATED | page searched; only generic administrator/TSS wording unrelated to the remediation |
| veeam-vbr:hyperv:on-host-proxy-or-integration-failure (KB1857), object-storage immutability, restore:entire-vm-post-restore-differences, sobr:cannot-add-repository-as-extent, sobr:maintenance-mode-breaks-active-chain, surebackup:verification-failed (3 pages) | all eight | NOT STATED | pages searched for rollback/permission/verification/healthy-state; only warnings already in the record were found |
Limits of this research: HTML was read as text; the two Fortinet community pages render mostly with scripts, so unsearchable content cannot be excluded; "not stated" means "not found in the cited page", not "the vendor never documents it". No other vendor page (release notes, other KBs) was searched. Version applicability for the Fortinet and Veeam records is as already recorded in each record.

## Manual Review Package: 5 Cisco sources (not reviewed; cisco.com returned 403 to automated access and was not bypassed)
| Record key | URL | Section to inspect | Version applicability to confirm | Reviewer question | Evidence required | Fields left unverified |
|---|---|---|---|---|---|---|
| cisco-asa:failover:split-brain | https://www.cisco.com/c/en/us/support/docs/security/adaptive-security-appliance-asa-software/217691-troubleshoot-split-brain-issues-on-asa-f.html | symptoms, causes, emergency recovery | ASA and FTD releases the document names | Required privilege? Rollback if the standby is forced? Post-recovery verification? | verbatim quote + date per field | all eight |
| cisco-ios:bgp:neighbor-down | https://www.cisco.com/c/en/us/support/docs/ip/border-gateway-protocol-bgp/218027-troubleshoot-border-gateway-protocol-bas.html | neighbor states, remediation | IOS/IOS XE versions named | Destructive steps (clear)? Verification of Established state? | same | all eight |
| cisco-ios:bgp:session-reset-on-interface-flap | https://www.cisco.com/c/en/us/support/docs/ip/border-gateway-protocol-bgp/22166-bgp-trouble-main.html | flap and reset causes | as stated on the page | Is a remediation stated? Risk of a hard reset? | same | all eight |
| cisco-ios:interface:errdisable | https://www.cisco.com/c/en/us/support/docs/lan-switching/spanning-tree-protocol/69980-errdisable-recovery.html | errdisable recovery | platforms the page names | Is shutdown/no shutdown the stated recovery? Rollback? Verification? | same | all eight |
| cisco-nxos:ospf:adjacency-problems-nexus-7000 | https://www.cisco.com/c/en/us/support/docs/switches/nexus-7000-series-switches/116422-technote-ospf-00.html | adjacency states, fixes | NX-OS releases named | Required role? Impact of a config change? Verification? | same | all eight |
No review event exists or was created for any Cisco record; none is approved.

## Remaining
Human reviewers must read the five Cisco pages and verify/approve through the reviewer workflow. Further vendor sources for the nine unresolved records (release notes, other KBs, product manuals) have not been searched.

See `cisco_five_page_review_assignments.md` for per-page reviewer competencies, accessibility, version-scope questions and worksheets, and `reviewer_sourcing_and_qualification_report.md` for who should review. The 16-record research was not repeated in the third pass.
