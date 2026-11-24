# Knowledge source verification packet — 2026-11-20

Recomputed state (current code): 175 records = 153 `operational_context` + 22 `diagnostic_candidate`. Candidates: 16 `official_documentation_verified` (reference verified, **not** approved), 4 `code_supported_with_contextual_reference`, 2 `code_supported`. Structured `diagnostic_guidance` exists on **7 of 22** (Cisco ASA 106023, 106024, 113005, 113019, 302013, 302014; OpenSSH AUTH-FAIL). **0** records are source-verified-by-a-human, validated or approved. Nothing in this packet changes any lifecycle state; promotion needs the existing independent reviewer (`/api/v1/knowledge/proposals` workflow).

## Research performed this round (honest account)
| Target | Source opened | Result |
|---|---|---|
| Palo Alto TRAFFIC/THREAT/SYSTEM/CONFIG (4 candidates) | `docs.paloaltonetworks.com` PAN-OS 11.1 syslog field descriptions | **Not readable**: the fetch tool refused the domain (network/policy). No claim added. |
| Fortinet traffic/utm/event categories (5 candidates) | docs.fortinet.com FortiOS 7.4.0 Log Message Reference, "Log message fields" | Page opened; the readable portion is a table of contents and does not define the category semantics (page text is 268k chars; only the first 100k were returned, with no definitions in them). **Still no readable source**; records stay candidate/reference-only. |
| Cisco ASA 106023/106024/113005/113019/302013/302014, OpenSSH AUTH-FAIL | Previously collected (2026-11-19): Cisco ASA syslog reference, OpenSSH `auth.c` | Guidance present, inferences labelled; **human re-read pending**. Not re-researched. |

No guidance was written this round for any source that was not opened and read. Record count was not increased.

## Prioritised source-verification packet (for the owner / reviewer)
1. **Cisco ASA 6 records with guidance** (highest value, guidance already drafted): reviewer re-reads the Cisco ASA Series Syslog Messages pages for each ID and confirms: message meaning, severity, parameters, and that every remediation step is supported or labelled inference. Then submit through the review workflow.
2. **OpenSSH AUTH-FAIL**: confirm `auth.c` log strings and the version scope claimed.
3. **Veeam/VMware (6 candidates, code-supported)**: need vendor KB/KB-article sources (Veeam KB for CBT/snapshot chain; Broadcom/VMware KB for missing snapshot file/CBT reset). Not researched (not opened).
4. **Fortinet (5)**: need a readable FortiOS log-type/subtype definition (Log Message Reference "Log types and subtypes" section, e.g. offset >100000 of the 7.4.0 page, or the PDF).
5. **Palo Alto (4)**: need the PAN-OS syslog field description pages (blocked domain here; open from a normal browser or provide an export).
6. **Hitachi JP1 `KAVT0000`, `KAVT0245-E`**: need the JP1 product family/version and the official message manual; until then they stay outside the canonical catalog.
7. **32 migrated Windows records with 0 official references**: add Microsoft Learn event references per provider; none is claimable as verified today.

## Quality gate reminder
A record is ready for independent approval only when provider/product identity, meaning, applicability, expected findings, diagnostic checks, remediation, risk, rollback, verification criteria and source evidence are each supported by an opened source. Sources that support only the definition keep the definition and mark remediation unavailable.
