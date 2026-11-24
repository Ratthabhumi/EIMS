# Knowledge Expansion Plan (2026-11-19)

Starting point: **22 validated diagnostic entries** + **141 operational
context entries** (not interchangeable).

## Milestones (targets, not quotas)

| Milestone | Validated entries | Entry condition |
|---|---|---|
| Now | 22 | audit complete (this document set) |
| Stage 1 | 250–300 | fill Windows server-role and Linux gaps; remediation/verification fields designed and applied |
| Stage 2 | 500 | multi-vendor scenario coverage (Veeam job chains, VMware datastore/HA, FortiGate VPN, ASA failover, PAN-OS policy) |
| Stage 3 | 1,000+ | only with per-entry source verification and quality-gate pass |

No milestone is met by duplicating wording or by promoting context entries to
"diagnostic" without the required sections.

## Sequence

1. **Schema first** (blocking): add `remediation`, `verification`, `verified_at`,
   `source_kind` to the diagnostic model; migrate the 22 entries; then the 141
   operational entries can be enriched incrementally without a second migration.
2. **Close the worst gaps** in this order:
   - Linux/OpenSSH (1 entry) → authentication, sudo, systemd, disk, network.
   - Windows server roles: AD/DS, DNS, RDP, storage, scheduled tasks.
   - Veeam (4) → job/repository/proxy/snapshot failure chains.
   - VMware (2) → datastore, HA/DRS, vCenter connectivity.
   - FortiGate / ASA / PAN-OS → the operational events already parsed.
3. **Cross-product scenarios** last: they need evidence from more than one
   product and are the highest-value, highest-effort entries.
4. **Promotion rule**: an operational entry becomes a diagnostic entry only when
   sections 4–9 of the quality standard are filled and sourced.

## Explicitly out of scope for this round

No new entries were added. Adding them requires per-entry vendor verification,
which was not performed, and the catalog must not grow by unsourced text.

## Definition of done for a future expansion round

- Validated count reported separately from context count.
- Every new entry passes the automated gates.
- 100% of validated entries carry a verification date and a source kind.
- Retrieval tests (exact code, product, version, no-match) pass on the new data.
