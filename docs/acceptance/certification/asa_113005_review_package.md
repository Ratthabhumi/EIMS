# ASA 113005 independent review package (prepared 2026-11-22; NOT reviewed)

Record: `cisco_asa:official_message_id:113005` (class B, ELIGIBLE by adapter, content hash `71731be15a7355e59f18613d0d6ddd03dbbe75f3fa8234e28363163b839cbaec`, lifecycle `candidate`, 0 human decisions). Nothing in this package is a review, verification or approval; reviewer fields are blank on purpose.

## Evidence provenance (be strict)
* Primary source: Cisco Secure Firewall ASA Series Syslog Messages 101001 to 199027, https://www.cisco.com/c/en/us/td/docs/security/asa/syslog/asa-syslog/syslog-messages-101001-to-199021.html . cisco.com refused automated page fetches earlier (HTTP 403, not bypassed). The statements below about the message come from a **search-result summary of the official page on 2026-11-22**, not from a verbatim read; the reviewer must read the page and copy quotes with the date.
* Supporting sources found by search (titles/URLs from the search result, content not read in full): ASA command reference `show aaa-server` (https://www.cisco.com/c/en/us/td/docs/security/asa/asa-cli-reference/S/asa-command-ref-S/show-aa-to-show-asr-commands.html); ASA TACACS+ and RADIUS server configuration chapters (e.g. https://www.cisco.com/c/en/us/td/docs/security/asa/asa919/configuration/general/asa-919-general-config/aaa-radius.html); Cisco hardening guidance for Secure Client VPN (https://www.cisco.com/c/en/us/support/docs/security/secure-client/221880-implement-hardening-measures-for-secure.html); Cisco advisory on RAVPN brute-force (https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-asaftd-bf-dos-vDZhLqrW). A page titled "Analyze AAA Device Administration Behavior for ASA" and a "Testing TACACS+ Authentication and Authorization" page were **not found by search**; they must be located by the reviewer before being cited.

## Message definition (to be confirmed against the page)
| Item | Claim from the search summary | Reviewer must confirm |
|---|---|---|
| Authentication variant | `%ASA-6-113005`: "AAA user authentication Rejected"; fields: reason, AAA server IP, username, user IP; meaning: AAA authentication on a connection failed; recommended action: retry the authentication | exact syntax, severity and field order |
| Authorization variant | a second 113005 entry for "AAA user authorization Rejected" with the same fields; recommended action: retry the authorization | that the two variants are distinct entries and how the log distinguishes them |
| Username masking | username hidden when invalid or unknown; shown if valid or if `no logging hide username` is configured | exact wording; effect on diagnosis |
| FTD | Firewall Threat Defense lists the same message in its syslog guide | whether the catalog's "ASA only" scope (FTD/PIX parsing retained without claiming applicability) is right |
| Version applicability | not established by any source read | release range for the message and for the masking behavior (Cisco "Version and Message History" page) |
The EIMS record currently states: what happened, why (the same sentence, not an independent cause), inspect (4 items), recommended action (retry, source wording), risk (repeated retries with a wrong secret can lock the account on the AAA server), rollback ("Not applicable: a retry changes no configuration"), recovery verification (retried attempt accepted and no further 113005 for the same user and source). **Not stated:** required permission, human-approval wording from the vendor, recovery evidence, success criteria, operational impact, destructive risk.

## Questions each reviewer must answer
Authentication vs authorization (Reviewer A/B): does the EIMS parser separate the two variants and never present an authorization rejection as a credential failure? Does the record's "why" overstate cause? (The record's "why" repeats the meaning; it is not a root cause.)
Hypotheses, to be labelled hypotheses and never "confirmed" without correlation: wrong or expired credentials; user not found or locked in the AAA store; policy or authorization-profile denial; AAA server unreachable or timing out; shared-secret mismatch (RADIUS "bad authenticators"); server-side memory or resource errors reported as the reason; brute-force or password-spray traffic (a large number of rejects may indicate an attack per the Cisco advisory summary).
Diagnostics (verify wording and commands against Cisco pages): the reason string in the log; `show aaa-server` counters (accepts, rejects, timeouts, bad authenticators) read several times a few seconds apart; AAA server status (FAILED vs active); the AAA server's own log for the same user and timestamp; the test command for the AAA server from the ASA (reviewer to confirm the exact command and release).
**Correlation requirement:** a single ASA syslog line cannot prove root cause or recovery. A confirmed cause needs the matching AAA-server log entry for the same user, source IP and time window; recovery needs a successful authentication/authorization correlated to the original user and source, with no new 113005 for them.
Safety (Reviewer C): no recommendation to reset passwords, change AAA policy, disable authentication or change server configuration unless a source states it and an approver accepts the operational risk (lock-out of administrators, VPN/remote-access outage). Required permission (privilege level to run `show aaa-server`, access to AAA server logs), backup need (none for read-only checks; configuration backup before any AAA change), rollback for any change, post-check and healthy-state criteria (counters stop climbing, server active, successful authentication for the affected user) must each be sourced or left NOT STATED.

## Worksheet (one per reviewer, filled independently; do not read another reviewer's sheet first)
Record key: `cisco_asa:official_message_id:113005` (content hash above). Source URL: https://www.cisco.com/c/en/us/td/docs/security/asa/syslog/asa-syslog/syslog-messages-101001-to-199021.html (the reviewer must read the original page; a search snippet is not a source). Product/version scope under review: Cisco ASA (and FTD where stated), releases to be confirmed. Exact technical question: does the page, read directly, support each statement in the EIMS record and does the record keep authentication rejection and authorization rejection apart?
Reviewer role: ____ (A Cisco ASA/firewall; B AAA/identity; C network security operations). Required competencies for this role: see `reviewer_sourcing_and_qualification_report.md`. Reviewer name: ____. Verifiable qualification evidence (what and where checked): ____. Conflict-of-interest declaration (authorship of this record, employment by Cisco or EIMS vendors, financial interest, prior involvement in preparing the evidence): ____. Date: ____. Signature or other owner-defined attestation: ____.
| # | Question | Source page and verbatim quote | Verdict (supported / not supported / needs change) | Notes |
|---|---|---|---|---|
| 1 | Message syntax and both variants | | | |
| 2 | Version applicability (ASA and FTD) | | | |
| 3 | Masking behavior | | | |
| 4 | "Why" and cause hypotheses labelled as hypotheses | | | |
| 5 | Diagnostic commands and permissions | | | |
| 6 | Remediation safety and impact | | | |
| 7 | Rollback / backup | | | |
| 8 | Post-check, recovery evidence, healthy state | | | |
| 9 | Parser mapping correct for authentication vs authorization | | | |
Decision recorded by the system only through the reviewer workflow (source_verified, validated, approved) under the reviewer's own session; this worksheet is supporting evidence, not the decision.

**Independent conclusion (write before reading any other reviewer's sheet):** supported as written / supported with the listed changes / not supported; reasons: ____
**Risk and recovery questions that must be answered in writing:** What can go wrong if an engineer follows the record (account lock-out on the AAA server, loss of administrator or VPN access)? What evidence shows recovery for the same user and source, and what would show that recovery has not happened? What must be backed up or confirmed before any AAA change?
**Source access status:** original Cisco page NOT yet read by anyone; HTTP 403 to automated retrieval; no direct source verification is claimed.
