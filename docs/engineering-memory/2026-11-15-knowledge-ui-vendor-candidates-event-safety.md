# EIMS finalization delta — Knowledge UI, vendor source candidates and event safety (2026-11-15)

## Scope and preservation

- Work executed on Mew through Remote Desktop Commander only.
- Branch: `integration/eims-consolidated`.
- HEAD remains `85493b2131d3e353453072559a5dfc301d75dd06`.
- Existing modified/untracked work preserved. No reset, clean, stash, commit, push, or operational DB access.
- No new production/operational Knowledge records were inserted.

## Knowledge Lifecycle Dashboard

Updated `clients/dashboard/src/app/knowledge/page.tsx` to expose the existing admin lifecycle API:
- Admin-only revalidation queue.
- Revalidate/reactivate, supersede (requires replacement ID), and withdraw actions.
- Required reviewer reason and evidence note.
- Admin-only lifecycle event history.
- Active approved entries expose require-revalidation and withdraw controls.
- Lifecycle history is not exposed to ordinary Engineer UI because the API is admin-scoped.

Production build after these UI changes:
- Next.js compile: PASS.
- TypeScript: PASS.
- Static pages: 15/15.
- Exit code: 0.
- No new Browser Acceptance run was performed after these UI changes; do not claim Browser Acceptance for the lifecycle UI.

## Official vendor source candidate corpus

Created:
- `docs/knowledge-source-candidates/official-vendor-candidates.v1.json`
- `docs/knowledge-source-candidates/README.md`
- `tests/test_knowledge_source_candidates.py`

20 structured candidates, aligned where possible to exact signatures present in the synthetic Gold fixtures:
- Microsoft (5): Event 4625, Event 4740, Advanced Audit Policy, Event 1129, Event 6005.
- Broadcom VMware (6): KB 450303, KB 324542, KB 309348, KB 442155 (CTK unlink/result 2620), KB 424591 (snapshot revert missing file), KB 343510 (snapshot consolidation).
- Veeam (4): VBR 13 backup health check, SureBackup recovery verification, backup verification, REST API session/task logs for generic Failed outcomes.
- Fortinet (5): FortiOS event logs, debug flow, IPsec in HA, traffic log ID 0000000013, configuration object log ID 0100044547.
Specific fixture alignment includes Windows 1129/6005, VMware/Veeam CTK unlink result 2620, VMware InvalidSnapshotFormat/missing snapshot file, Fortinet forward traffic action and configuration-object change. These fixtures remain synthetic and DRAFT; this mapping does not validate Gold truth or approve Knowledge.

Every candidate has exact product/version scope, applicability, prerequisites, evidence to collect, limitations, next checks, validation, rollback, risk and reviewer state.

**Trust boundary:** all candidates remain `pending_domain_review` and `candidate_only_not_approved_knowledge`. They are not imported into `knowledge_entries`, are not exposed to exact-identity retrieval and are not published as approved fixes. A vendor document establishes documented product behavior/scope; it does not establish the local incident's root cause or prove a remediation worked in the organization's environment.

No stale review interval was invented. Revalidation triggers are vendor revision, product EOL/support changes, security advisory, version/topology drift, failed usage feedback or contradictory evidence.

## Legacy static Event Knowledge safety corrections

Reviewed `backend/domain/analyzer/services/event_knowledge.json` and identified unsafe or overconfident generic advice. Added reproducible hardening script:
- `tools/harden_static_event_knowledge.py` (dry-run by default; explicit `--apply` required).
- 21 targeted event entries now use evidence-first diagnostics and safe change boundaries.
- Every cause statement in all 39 event entries is explicitly qualified as a hypothesis to verify.
- Examples hardened: 4624, 4625, 4720, 4740, 7000, 7034, 7009, 11, 51, 1014, 134, 1511, 20, 1135, 10016, 17, 4771, 55, 4768, 1102, 4672, 4688 and JP1 KAVT0000.

High-impact corrections include:
- No blanket IP blocking or password reset from a single authentication event.
- No automatic brute-force assertion from 4625/4740/4771 alone.
- No deleting ProfileList keys or rebooting as a first response to 1511.
- No global disabling of endpoint protection/firewall.
- No CHKDSK repair mode before backup, volume, workload and maintenance impact review.
- No registry timeout or DCOM ACL changes without vendor guidance and approved rollback.
- No cluster heartbeat threshold changes from one event.
- No firmware update, storage replacement or pool rebuild without diagnostic evidence and owner approval.
- No public VirusTotal upload of customer files/data.

Also corrected high-risk operator context in `operational_event_catalog.json`:
- Event 4625 no longer says high frequency proves brute force or instructs direct IP blocking.
- Disk Events 7/51 no longer prescribe immediate hardware replacement.
- Event 55 no longer directs immediate CHKDSK and no longer assumes every affected volume is read-only.
- Event 98 no longer directs enabling integrity streams or rebuilding a pool without topology/version/vendor review.

## Verification

- JSON parse validation: event_knowledge, operational_event_catalog and candidate corpus all valid.
- Focused suite: **53 passed, 0 failed**, exit code 0.
  - `tests/test_knowledge_source_candidates.py`
  - `tests/test_event_knowledge_safety.py`
  - `tests/test_diagnostic_catalog.py`
- Targeted Ruff F401/UP017: PASS, exit 0.
- Python compileall: PASS, exit 0.
- `git diff --check`: PASS, exit 0 (existing line-ending warnings only).

The focused suite verifies all 39 event-catalog cause statements are explicitly hypotheses, high-impact static recommendations no longer contain selected unsafe directives, authentication events do not claim brute force from a single event, and all 12 candidate records remain review-gated with validation/rollback.

## Official vendor references used

- Microsoft Event 4625: https://learn.microsoft.com/windows/security/threat-protection/auditing/event-4625
- Microsoft Event 4740: https://learn.microsoft.com/en-us/previous-versions/windows/it-pro/windows-10/security/threat-protection/auditing/event-4740
- Microsoft Advanced Audit Policy: https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/plan/security-best-practices/advanced-audit-policy-configuration
- Broadcom KB 450303: https://knowledge.broadcom.com/external/article/450303/esxi-host-network-connectivity-issues-fo.html
- Broadcom KB 324542: https://knowledge.broadcom.com/external/article/324542/
- Broadcom KB 309348: https://knowledge.broadcom.com/external/article?articleId=309348
- Veeam VBR 13 Health Check: https://helpcenter.veeam.com/docs/vbr/userguide/backup_health_check.html?ver=13
- Veeam SureBackup: https://helpcenter.veeam.com/docs/vbr/userguide/surebackup_recovery_verification.html
- Veeam Backup Verification: https://helpcenter.veeam.com/docs/vbr/userguide/sch_backups_verify.html
- Fortinet FortiOS 8.0.0 Event Logs: https://docs.fortinet.com/document/fortigate/latest/administration-guide/536166/viewing-event-logs
- Fortinet FortiOS 8.0.0 Debug Flow: https://docs.fortinet.com/document/fortigate/8.0.0/administration-guide/54688/debugging-the-packet-flow
- Fortinet FortiOS 8.0.0 IPsec HA: https://docs.fortinet.com/document/fortigate/8.0.0/administration-guide/111309

## Remaining gates

- Domain reviewer must review the source candidates and approve incident-backed Knowledge independently.
- The production approved Knowledge corpus remains insufficient; candidate records are not a substitute.
- Gold DEV 12 still requires independent human review; 5 HELDOUT cases remain sealed until Gold freeze.
- External/offsite PostgreSQL backup target, retention/encryption policy, BIA-approved RPO/RTO, failover and witnessed restore remain outstanding.
- Lifecycle UI has a successful production build but still needs a Browser Acceptance pass against a synthetic admin account and synthetic lifecycle records.
- Controlled Engineer pilot remains blocked on domain and operational sign-off.

## Final interpretation

The lifecycle controls are now accessible in the admin UI, a 12-record official-source candidate pack exists, and risky legacy event advice was made evidence-first. EIMS is not closed: candidate sources are not approved Knowledge, human review is still required, and operational recovery evidence must be collected on a separate failure domain.
