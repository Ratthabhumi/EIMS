# Knowledge Coverage Matrix (2026-11-19)

Legend: **V** validated diagnostic entries · **C** context-only event entries ·
**G** gap (no entries) · **—** not a knowledge concern.

| Product family | V | C | Investigation | Sources | Version scope | Verdict |
|---|---|---|---|---|---|---|
| Microsoft Windows (event log) | 0 | 141 | no | no | no | **context layer only** |
| Cisco Secure Firewall ASA | 6 | 0 | yes | yes | yes | covered (6 entries) |
| FortiGate / FortiOS 6.2.14 | 5 | 0 | yes | yes | yes (single version) | covered, version-thin |
| Veeam Backup & Replication | 4 | 0 | yes | yes | yes | thin (4) |
| PAN-OS default CSV syslog | 4 | 0 | yes | yes | parser-scoped | parser-oriented |
| VMware vSphere/ESXi | 2 | 0 | yes | yes | yes | thin (2) |
| Linux / OpenSSH | 1 | 0 | yes | yes | yes | minimal (1) |
| Windows Server roles (AD, DNS, RDP, storage) | 0 | (inside Windows C) | no | no | no | **gap: context only** |
| Structured JSON parsers | 0 | 0 | — | — | — | parser capability, not knowledge |

## Coverage dimensions still unsupported

- **Remediation** and **verification** do not exist as fields in either tier, so
  no entry can be measured on them.
- **Version ranges** exist only for the 22 diagnostic entries; the 141 operational
  entries are version-agnostic context.
- **Category balance**: authentication, services, storage and PowerShell are the
  best-populated Windows categories; AD/DS, RDP, DNS troubleshooting and
  Linux systemd/journald are effectively uncovered.
- **Cross-product correlation** (e.g. Windows event ↔ Veeam job failure ↔ VMware
  datastore alarm) has no entries at all.

## Practical reading

The catalog is usable today as **event context + 22 diagnostic playbooks**. It is
not yet a balanced multi-vendor diagnostic base, and the UI should say so.
