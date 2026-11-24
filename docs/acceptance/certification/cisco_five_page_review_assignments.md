# Cisco five-page manual review: assignments and worksheets (prepared 2026-11-22; NOT reviewed)

All five pages are on cisco.com, which returned HTTP 403 to automated access; they were not bypassed and **not read by EIMS tooling**. Human review is still required for every page. No page is marked reviewed; no `source_verified`, `validated` or `approved` event exists for these records. The five are **not all ASA**: assign by product domain.

| # | Record key | Product / domain | URL | Page accessible to automation | Reviewer competency (not an ASA specialist unless stated) | Version scope to confirm |
|---|---|---|---|---|---|---|
| 1 | cisco-asa:failover:split-brain | Cisco ASA / FTD high availability | https://www.cisco.com/c/en/us/support/docs/security/adaptive-security-appliance-asa-software/217691-troubleshoot-split-brain-issues-on-asa-f.html | No (403) | ASA/Secure Firewall HA specialist | ASA and FTD releases named on the page |
| 2 | cisco-ios:bgp:neighbor-down | Cisco IOS routing (BGP) | https://www.cisco.com/c/en/us/support/docs/ip/border-gateway-protocol-bgp/218027-troubleshoot-border-gateway-protocol-bas.html | No (403) | routing / BGP specialist | IOS/IOS XE releases named |
| 3 | cisco-ios:bgp:session-reset-on-interface-flap | Cisco IOS routing (BGP) | https://www.cisco.com/c/en/us/support/docs/ip/border-gateway-protocol-bgp/22166-bgp-trouble-main.html | No (403) | routing / BGP specialist (may be the same person as #2 if independent of the record's author) | as stated on the page; the document is old (Document ID 22166), so applicability needs explicit confirmation |
| 4 | cisco-ios:interface:errdisable | Cisco IOS/Catalyst switching | https://www.cisco.com/c/en/us/support/docs/lan-switching/spanning-tree-protocol/69980-errdisable-recovery.html | No (403) | LAN switching / Catalyst specialist | platforms listed on the page |
| 5 | cisco-nxos:ospf:adjacency-problems-nexus-7000 | Cisco NX-OS (Nexus 7000) routing | https://www.cisco.com/c/en/us/support/docs/switches/nexus-7000-series-switches/116422-technote-ospf-00.html | No (403) | data-centre / NX-OS routing specialist | NX-OS releases and Nexus 7000 only; confirm it does not extend to other Nexus lines |
Each record currently carries a vendor-derived remediation but no `operational_fields`; the contract blocker is "High/Critical risk knowledge requires validation and rollback steps", i.e. rollback, permission and verification are unstated in EIMS.

## Worksheet (copy per page; one reviewer per sheet, independent)
Record key: ____ Source URL: ____ (read the original page; no snippet) Product/version scope under review: ____ Exact technical question: does the page, read directly, support each remediation, risk and verification statement in the EIMS record, for the stated versions? Required competency: see the assignment table. Reviewer name: ____ qualification evidence (what and where checked): ____ conflict-of-interest declaration (authorship, employer or vendor relationship, prior involvement): ____ date: ____ attestation: ____
| Field | Question | Quote from the page (verbatim) and section | Stated / Unverified / Not stated | Unsupported claim in the EIMS record |
|---|---|---|---|---|
| required_permission | What privilege or role is needed for each step? | | | |
| human_approval_required | Does the page warn that a step needs approval or a maintenance window? | | | |
| rollback_steps | How is each state change undone? | | | |
| verification_steps | How is recovery confirmed? | | | |
| recovery_evidence | Which output proves recovery? | | | |
| recovery_success_criteria | What is the healthy state? | | | |
| operational_impact | What breaks or is interrupted? | | | |
| destructive_risk | Which step can lose data or connectivity (for example clearing a BGP session, forcing a failover, disabling failover on a unit, shutting interfaces)? | | | |
Page-specific points: #1 steps such as disabling failover on one unit and shutting its interfaces are state-changing and can isolate a firewall; #2/#3 `clear ip bgp` style actions reset sessions; #4 errdisable recovery that re-enables a port may re-trigger the cause; #5 OSPF configuration changes can drop adjacencies. These are prompts for the reviewer, not claims taken from the pages.
Outputs go into the catalog only after the reviewer's verbatim quotes are entered through the reviewer workflow (draft → human review → decision).
**Independent conclusion (before reading another reviewer's sheet):** supported / supported with changes / not supported; reasons: ____
**Risk and recovery questions:** what can a step in this record interrupt (sessions, adjacencies, ports, failover), what proves recovery, and how is a state change undone?
**Source access status:** all five pages returned HTTP 403 to automated retrieval; none has been read by anyone for this project; no direct source verification is claimed.
