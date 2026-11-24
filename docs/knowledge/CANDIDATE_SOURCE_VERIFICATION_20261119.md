# Diagnostic candidate source verification — 2026-11-19 (milestone 5, part G)

**Status: source-evidence collection only. No candidate was promoted.** Nothing was written to any database (operational or disposable). All 22 records stay `candidate` in the governance lifecycle.

## Method and limits (read first)
- Sources were fetched on 2026-11-19 with a page-fetch tool that returns a *model-generated extraction* of each page, not the raw page. Quoted text below is as extracted; a human verifier must re-read each source before `source_verified` is recorded. This is AI-assisted evidence gathering, not a human review.
- `source_verified` needs an authenticated human `verifier` (gate: verifier must equal the actor). `validated` needs a reproducible validation basis (lab run). `approved` needs a third independent person. None exist yet, so no promotion is attempted and nothing is inferred as approved.
- Verification dates are the fetch date; no vendor page states an EIMS-relevant software version unless noted.

## Disposition summary (22 records)
| Group | Records | Result |
|---|---|---|
| Cisco ASA 106023, 106024, 113005, 113019, 302013, 302014 | 6 | Message text, explanation and recommended action machine-read from the Cisco page. **Evidence collected**, with title/scope caveats below. |
| OpenSSH `AUTH-FAIL` | 1 | Log format string read from `auth.c` (master, unpinned). **Evidence collected**, source code not vendor doc. |
| PAN-OS TRAFFIC / THREAT / SYSTEM / CONFIG | 4 | Field layouts read. **Partial**: the pages do not call the layout "default CSV" and do not name one PAN-OS version. |
| VMware snapshot file missing (Veeam + VMware records) | 2 | Broadcom KB 424591 supports a **narrow** vCenter-revert claim only. **Partial**. |
| Change tracking file deletion failed (Veeam + VMware records) | 2 | Related CBT KBs found, none describes this signature. **Partial / not established.** |
| Veeam replica chain, Veeam session failed | 2 | Cited KB1832 is log collection only. **Supports a next-step, not a diagnosis.** |
| FortiOS traffic/forward, utm/ips, event/vpn, event/user, event/system | 5 | **NOT verified**: cited PDF has no text layer; HTML page truncated. |

## Per-record evidence

### Cisco ASA (source: Cisco Secure Firewall ASA Series Syslog Messages; page "Updated: September 22, 2026"; no software version on the page, so version scope is NOT established)
- **106023** — `%ASA-4-106023: Deny … by access-group …`. Explanation: "A real IP packet was denied by the ACL." Appears even when logging is not enabled on the ACL. Action: repeated messages from one source "might" indicate footprinting/port scanning. Limitation: a denial is policy behaviour, not a fault. URL: `…/syslog-messages-101001-to-199021.html`.
- **106024** — `%ASA-2-106024: Access rules memory exhausted…`. Explanation: ACL compilation ran out of memory; the previous compiled lists stay in use and changes since the last successful compilation are removed. Action: remove rules (ACL/AAA/ICMP/SSH/Telnet rule types all count). Verification criterion supported by source: a later compilation completes without the message (inference; the page does not state a check).
- **113005** — two variants exist: *authentication* and *authorization* "Rejected". Explanation: AAA authentication/authorization failed; the username is hidden when invalid or unknown. Action: "Retry the authentication" / "Retry the authorization." **Caveat:** the EIMS title covers authentication only.
- **113019** — `%ASA-4-113019: Group …, Username …, IP …, Session disconnected. Session Type …, Duration …, Bytes xmt/rcv …, Reason …`. Explanation per source: "An indication of when and why the longest idle user is disconnected." Action: none unless the reason indicates a problem. **Caveat:** the EIMS title "VPN session disconnected" is broader than the source's explanation; wording should be reviewed.
- **302013 / 302014** — TCP connection built / teardown. Action per source: "None required." Teardown includes a reason table (e.g. Conn-timeout = inactivity timer expired). These are context records with no remediation; they should not be treated as faults.

### OpenSSH `AUTH-FAIL`
`auth.c` (`auth_log`, openssh-portable master) builds `"%s %s%s%s for %s%.100s from %.200s port %d ssh2%s%s"` with `authmsg` of "Accepted", "Failed", "Partial" or "Postponed", and inserts `invalid user ` when the user is not valid. This supports the "Failed password … from … port … ssh2" signature. Limitations: unpinned `master` branch (not a release), method text ("password") comes from the caller, source code rather than vendor documentation.

### PAN-OS log fields (docs.paloaltonetworks.com; "Updated Oct 30, 2026" on two pages)
- Traffic/Threat: "Format" lists FUTURE_USE, Receive Time, Serial Number, Type, Threat/Content Type, FUTURE_USE, Generated Time, Source Address, Destination Address, … (15+ fields). Some fields are release-gated (11.1+, 12.1.2+); TCP telemetry fields are "intended for internal use".
- System: Format is FUTURE_USE, Receive Time, Serial Number, Type, Content/Threat Type, FUTURE_USE, Generated Time, Virtual System, Event ID, Object, …, Module, Severity, Description, … (26 fields).
- Config: Format includes Host, Virtual System, Command, Admin, Client, Result, Configuration Path, Before/After Change Detail, … The page says Before/After Change Detail are **custom-log only** while also listing them in the format line (the page is internally inconsistent).
- **Not established:** that this is the "default CSV syslog" layout, and a single PAN-OS version (navigation spans 8.1–12.2). The catalog scope text must stay conservative.

### Broadcom KB 424591 → VMWARE-SNAPSHOT-FILE-MISSING (Veeam + VMware records)
Reverting a snapshot fails with "A required file was not found" (`vim.fault.InvalidSnapshotFormat`, "Detected an invalid snapshot configuration", key `msg.snapshot.vigor.revert.error`, argument `msg.snapshot.error-NOTFOUND`). Applies to ESXi 8.0 / vCenter 8.0. Stated cause: the snapshot disk referenced by the VM does not exist. Resolution: place the missing snapshot disk in the VM directory, or restore from backup. **Limitation:** describes a vCenter *revert*; it does not describe a Veeam backup-job failure, so it supports the VMware-side record and only contextually the Veeam-side one.

### Change tracking file deletion failed (Veeam + VMware records)
- Broadcom KB 339974 (ESXi 6.x–8.x): reset CBT procedure; requires no active snapshots; VMs with snapshots cannot be reset by the script.
- Veeam KB1113 (modified 2025-01-03): symptom "CBT data is invalid, failing over to legacy incremental backup"; usual cause power loss; existing snapshots can prevent a successful reset; next job reads all disks.
- Search results (titles only, not fetched): Broadcom articles on locked/corrupt `-ctk.vmdk` files exist. **Not established:** that EIMS's "deletion failed" signature maps to any of these. Existing catalog note already says "official lock article not generalized"; keep it.

### Veeam KB1832 → VEEAM-REPLICA-SNAPSHOT-CHAIN, VEEAM-SESSION-FAILED
"How to Collect Logs for Veeam Backup & Replication" (modified 2026-09-15; B&R 11–13.1): Support Information wizard, web UI export, manual PowerShell/robocopy collection. Supports the next-evidence step "collect support logs"; makes **no** claim about replica snapshot chains or generic session failures.

### FortiOS (5 records) — NOT verified
The cited FortiOS 6.2.14 Log Reference PDF (5.9 MB) is image-only, so no text could be extracted. The FortiOS 6.2.0 HTML page was truncated before the subtype table. A search summary (secondary, not a source) reports traffic/forward and event/system, user, vpn subtypes and names IPS-related subtypes as botnet / malicious-url / signature; whether a `utm/ips` subtype exists as named in the catalog is **unconfirmed**. These records remain `official_documentation_verified` in the JSON catalog on the strength of earlier work; this pass could not reproduce that claim, so treat it as unconfirmed until a human reads pages 34–37 of the PDF.

## Next executable actions
1. A named human verifier re-reads the sources above and records `source_verified` via `promote(review=…)` on a **disposable** database (gate fields map to the evidence here).
2. Obtain a text-extractable FortiOS log-type reference (or OCR pages 34–37) and re-check the 5 Fortinet records.
3. Review catalog wording flagged above (113005 variants, 113019 title, PAN-OS "default CSV", Veeam-side use of KB 424591).
4. Validation (lab reproduction) and independent approval remain entirely outstanding for every record.
