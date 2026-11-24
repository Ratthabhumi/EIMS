"""Extend the official-source candidate catalogue with exact Gold-case evidence families.

Dry-run by default; --apply writes the JSON pack. Candidate records remain unapproved.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/knowledge-source-candidates/official-vendor-candidates.v1.json"

NEW = [
{
"id":"MS-WIN-1129-001","vendor":"Microsoft","product":"Windows Server Group Policy / Active Directory","version_scope":"Windows Server; verify exact client/server OS build, GPO processing mode and domain topology","domain":"Group Policy processing / domain-controller connectivity","identity":"Windows System Event 1129","title":"Applying Group Policy troubleshooting guidance — Event ID 1129","url":"https://learn.microsoft.com/en-us/troubleshoot/windows-server/group-policy/applying-group-policy-troubleshooting-guidance",
"applicability":"Use only when Microsoft-Windows-GroupPolicy Event ID 1129 records that Group Policy could not contact a domain controller due to network connectivity.",
"prerequisites":["Identify client, domain controller, site/subnet, network path and whether failure is startup-only or persistent.","Do not assume LDAP 389 is the cause; Microsoft describes it as one documented scenario."],
"evidence":["Full event XML and timestamp","Client DNS resolver and DC discovery result","GPSvc debug log if enabled under an approved diagnostic plan","Network trace showing LDAP/DC connectivity","Firewall/router counters and GPO processing result"],
"limitations":["The article's blocked LDAP 389 example is one scenario, not a universal cause.","Network initialization race, DNS/DC discovery, routing, firewall/IPsec and DC availability must be distinguished."],
"next_checks":["Verify DNS SRV/DC discovery and the selected DC.","Trace the actual path and confirm required directory-service ports from Microsoft documentation for the deployed configuration.","Correlate Netlogon 5719 and GroupPolicy events; check whether background refresh later succeeds."],
"validation":["Run an authorized Group Policy refresh after the approved network correction.","Confirm successful processing in GPSvc logs and resultant policy; verify no unrelated DC traffic regressed."],
"rollback":["Restore captured firewall/routing/GPO values if the approved change causes regression; remove temporary GPSvc debug settings after evidence capture."],
"risk":"medium","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"MS-WIN-6005-001","vendor":"Microsoft","product":"Windows Server EventLog","version_scope":"Windows Server; verify event provider and OS build because Event ID numbers are source-specific","domain":"boot/reboot timeline correlation","identity":"EventLog Event ID 6005","title":"Troubleshoot unexpected reboots using system event logs","url":"https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/troubleshoot-unexpected-reboots-system-event-logs",
"applicability":"Use EventLog 6005 as a boot-history marker and correlate with Kernel-General 12/13, Kernel-Power 41, User32 1074, EventLog 6008 and 6009.",
"prerequisites":["Verify event provider/source, computer and timestamp; Event ID alone is not globally unique."],
"evidence":["Event provider and IDs 12/13/41/1074/6005/6008/6009","Timestamp and timezone","1074 initiating process/user/reason when present","Crash/bugcheck, UPS/power and hardware records"],
"limitations":["6005 means the Event Log service started; it does not by itself prove why a reboot occurred or whether it was unexpected.","Use source/provider as well as numeric event ID."],
"next_checks":["Build a chronological sequence across the listed events.","Distinguish planned shutdown (1074/13) from unexpected shutdown (41/6008) using the actual source and neighboring evidence."],
"validation":["Confirm the reconstructed reboot timeline matches host uptime/boot time and an independent system or hypervisor record."],
"rollback":["Read-only investigation; remove temporary event filters/export artifacts only."],
"risk":"low","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"VMW-CTK-442155-001","vendor":"Broadcom VMware","product":"VMware vSAN ESA / VMware Cloud Foundation","version_scope":"Broadcom KB 442155: vSAN ESA snapshot CTK unlink failure; source states issue fixed in VCF 9.1. Confirm exact VCF/vSAN/ESXi build and support status.",
"domain":"Changed Block Tracking file deletion / vSAN ESA snapshot cleanup","identity":"DISKLIB-LIB_BLOCKTRACK result 2620 / CTK_CTKUNLINK","title":"Snapshot usage on ESA cluster is very high due to CTK file deletion failure","url":"https://knowledge.broadcom.com/external/article/442155/snapshot-usage-on-esa-cluster-is-very-hi.html",
"applicability":"Use only when vmware logs contain DISKLIB-CTK could not unlink tracking file / Could not delete change tracking file with result 2620 on vSAN ESA.",
"prerequisites":["Confirm vSAN ESA topology, VCF/ESXi build, snapshot inventory and backup/replication activity.","Preserve vmware.log/vmware-*.log and snapshot/CTK file inventory before cleanup."],
"evidence":["Exact CTK_CTKUNLINK/result 2620 message and timestamp","VM UUID, VMDK and CTK file paths","vSAN ESA and VCF version/build","Snapshot inventory and datastore capacity","Concurrent backup/replication tasks and Broadcom support bundle"],
"limitations":["The KB is specific to vSAN ESA and states a fix in VCF 9.1; do not assume the fix applies to other vSAN/ESXi releases.","The article says existing orphaned snapshot cleanup should be handled with Broadcom Support; do not delete CTK/snapshot files manually."],
"next_checks":["Check whether deployed VCF version includes the documented fix.","Escalate existing orphaned snapshot cleanup to Broadcom Support with logs and inventory."],
"validation":["After vendor-approved correction, confirm CTK unlink errors stop and snapshot usage/chain state returns to expected values.","Run a controlled backup/replication and verify CBT/snapshot processing completes."],
"rollback":["Do not manually remove CTK/snapshot files. Preserve original VM folder and snapshot metadata; follow Broadcom-directed recovery/rollback only."],
"risk":"critical","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"VMW-SNAPSHOT-424591-001","vendor":"Broadcom VMware","product":"VMware vSphere ESXi / vCenter Server","version_scope":"Broadcom KB 424591: ESXi 8.0 and vCenter 8.0. Validate exact build and storage type.",
"domain":"Snapshot revert / missing snapshot disk","identity":"vim.fault.InvalidSnapshotFormat + msg.snapshot.error-NOTFOUND","title":"Reverting a virtual machine snapshot fails with A required file was not found","url":"https://knowledge.broadcom.com/external/article/424591/reverting-a-virtual-machine-snapshot-fai.html",
"applicability":"Use when snapshot revert reports InvalidSnapshotFormat and A required file was not found, and vpxd.log identifies a missing snapshot disk referenced by the target VM.",
"prerequisites":["Confirm VM UUID, target snapshot, datastore availability and exact ESXi/vCenter versions.","Preserve VMX, VMSD, VMDK descriptors, snapshot tree and vpxd/hostd/vmware logs."],
"evidence":["Full InvalidSnapshotFormat fault and NOTFOUND message","Target snapshot ID and VM UUID","Referenced snapshot-disk path and datastore mount state","Snapshot tree and descriptor/parent CID chain","Recent backup/restore or manual file movement timeline"],
"limitations":["A missing referenced snapshot disk is the documented cause for this specific error; do not generalize to all snapshot failures.","Restoring or moving VMDKs can affect snapshot-chain consistency and data integrity."],
"next_checks":["Verify the referenced file path and datastore accessibility without changing files.","Compare VM configuration references with the actual snapshot disk inventory.","Engage Broadcom Support/storage owner before repairing the chain."],
"validation":["After approved recovery, verify snapshot tree consistency, VM power state and application-level data integrity.","Run a controlled backup and confirm it completes without snapshot-chain errors."],
"rollback":["Preserve a copy of the VM configuration and all disk descriptors before any approved repair; do not manually move/delete snapshot files without vendor-directed steps."],
"risk":"critical","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"VMW-SNAPSHOT-343510-001","vendor":"Broadcom VMware","product":"VMware vSphere ESXi / vCenter Server","version_scope":"Broadcom KB 343510 covers ESXi 6.x, 7.x and 8.x; verify exact build and storage topology.",
"domain":"Snapshot delete/consolidate failures","identity":"Snapshot consolidation A required file was not found","title":"An error occurred while consolidating disks when deleting or consolidating snapshots","url":"https://knowledge.broadcom.com/external/article/343510",
"applicability":"Use when snapshot delete/consolidation reports A required file was not found, missing virtual disk or snapshot disk, or related parent disk errors.",
"prerequisites":["Record VM power state, snapshot tree, datastore health/capacity and exact error.","Preserve all VM disk descriptors, logs and backup-chain state before remediation."],
"evidence":["vCenter task error and VM UUID","hostd/vpxd/vmware logs","Referenced VMDK/snapshot paths and parent CID","Datastore mount/capacity and storage-path health","Concurrent backup/replication/lock activity"],
"limitations":["A missing virtual disk/snapshot file at the configured path is one documented cause; lock, busy-disk, I/O and parent-CID mismatch are separate cases.","Do not delete files or consolidate manually without identifying the exact failure branch."],
"next_checks":["Match the exact error to the KB cause/resolution table.","Verify referenced files exist and datastores are mounted at the expected paths.","Use vendor support for uncertain or inconsistent snapshot chains."],
"validation":["Confirm snapshot delete/consolidation completes and VM disk chain remains consistent.","Run application-level checks and a controlled backup."],
"rollback":["Preserve VM folder, descriptors and snapshot metadata; use an approved backup/restore or vendor-guided recovery plan."],
"risk":"critical","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"VEEAM-VBR13-SESSION-001","vendor":"Veeam","product":"Veeam Backup & Replication 13 REST API","version_scope":"VBR 13 REST API 1.3-rev2; verify installed API version and role permissions.",
"domain":"Backup/replication session failed outcome investigation","identity":"VBR session result Failed / task-session log","title":"Veeam Backup & Replication 13 REST API — Get Session Logs","url":"https://helpcenter.veeam.com/references/vbr/13/rest/1.3-rev2/tag/Sessions/index.html",
"applicability":"Use when a Veeam job/replica session is marked Failed but the top-level status does not contain the underlying task failure.",
"prerequisites":["Authorized VBR API role (Backup Administrator/Operator/Restore Operator/Backup Viewer or approved custom role).","Capture session UUID and exact VBR/API build."],
"evidence":["Session UUID, job UUID, name and creation/end timestamps","Session result and message","GET /api/v1/sessions/{id}/logs records and task-session logs","Failed task title/description and preceding warning/success records","Source/target infrastructure and operation type"],
"limitations":["A generic Failed session status is an outcome, not a root cause.","API role and version constraints apply; task-session and session logs are distinct endpoints."],
"next_checks":["Retrieve session detail and full ordered logs for the exact failed session.","Identify the first failing task and correlate with VMware/Hyper-V/storage/network evidence."],
"validation":["After the underlying cause is corrected, run a controlled job and verify session result plus all task logs are successful."],
"rollback":["Read-only investigation; no backup-chain or job configuration changes are prescribed by this API reference."],
"risk":"low","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"FGT-TRAFFIC-0000000013-001","vendor":"Fortinet","product":"FortiGate / FortiOS Log Message Reference","version_scope":"FortiOS 7.6.0 log-message reference; confirm exact FortiOS build and traffic-log schema.",
"domain":"Forward traffic log interpretation","identity":"FortiGate logid 0000000013 / type traffic / subtype forward","title":"Log message fields — FortiGate / FortiOS 7.6.0","url":"https://docs.fortinet.com/document/fortigate/7.6.0/fortios-log-message-reference/357866/log-message-fields",
"applicability":"Use when logid 0000000013 appears in a FortiGate traffic forward log.",
"prerequisites":["Preserve the complete raw log; confirm type=traffic and subtype=forward.","Verify action, policyid, interfaces, addresses and FortiOS build."],
"evidence":["logid, type and subtype","action, policyid and policy UUID","srcip/srcport/srcintf and dstip/dstport/dstintf","proto, service, sessionid, duration, sent/received bytes","UTM action and security fields if present"],
"limitations":["Log ID 0000000013 identifies a forward traffic log, not an allow/deny verdict by itself.","The action field determines interpretation: Deny is policy blocked; Start is a session-start log that means allowed; other action values describe how an allowed session closed."],
"next_checks":["Interpret action with policyid and direction; do not infer denial from logid alone.","Correlate with policy/config change events and packet-flow evidence when traffic is unexpected."],
"validation":["Compare the expected test flow with raw log action, policy and byte counters in both directions."],
"rollback":["Read-only log interpretation; do not change firewall policy solely because this log ID is present."],
"risk":"low","review_state":"pending_domain_review","evidence_status":"official_source_verified"
},
{
"id":"FGT-CONFIG-0100044547-001","vendor":"Fortinet","product":"FortiGate / FortiOS","version_scope":"FortiGate configuration event log; source article does not specify a single FortiOS build, so verify the installed firmware and schema.",
"domain":"Firewall configuration object change audit","identity":"FortiGate logid 0100044547 / LOGID_EVENT_CONFIG_OBJATTR","title":"Difference between logid 0100044547 and 0100044546 when FortiGate configuration changes","url":"https://community.fortinet.com/fortigate-3/technical-tip-difference-between-logid-0100044547-and-logid-0100044546-which-are-generated-when-configuration-is-changed-in-the-fortigate-203472",
"applicability":"Use when FortiGate system event log contains logid 0100044547 indicating an object attribute configured event.",
"prerequisites":["Preserve raw event and verify FortiGate device/firmware.","Confirm authorized administrator, change ticket and management interface."],
"evidence":["user, ui, action and timestamp","cfgpath, cfgobj and cfgattr","msg and config transaction/change ID","Device serial, VDOM and firmware","Related 0100044546/0100044547 records"],
"limitations":["0100044547 indicates an object attribute was created/modified/deleted; it does not by itself prove malicious or unauthorized activity.","Interpret action and cfgpath/cfgattr; the change may be an approved administrator action."],
"next_checks":["Match user/UI/action/object path to approved change records.","Compare before/after configuration through approved FortiGate configuration history."],
"validation":["Confirm the final configuration matches the approved change and expected traffic/security behavior."],
"rollback":["Use the approved FortiGate configuration revision/backup and change rollback procedure; do not revert configuration from a single log event."],
"risk":"medium","review_state":"pending_domain_review","evidence_status":"official_source_verified"
}
]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(TARGET.read_text(encoding="utf-8"))
    existing = {item["id"] for item in data["candidates"]}
    duplicates = existing.intersection(item["id"] for item in NEW)
    if duplicates:
        # Idempotent after a completed import; never duplicate catalogue entries.
        if all(item["id"] in existing for item in NEW):
            print(f"Already applied: all {len(NEW)} candidate records exist; no changes made.")
            return
        raise SystemExit(f"Partial prior import detected; reconcile manually: {sorted(duplicates)}")
    if args.apply:
        data["candidates"].extend(NEW)
        data["policy"]["exact_identity_retrieval_enabled"] = False
        data["policy"]["production_knowledge_import_enabled"] = False
        TARGET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"ADDED {len(NEW)} candidate records; total={len(data['candidates'])}; none approved.")
    else:
        print(f"DRY RUN: would add {len(NEW)} candidates; current={len(data['candidates'])}; new total={len(data['candidates']) + len(NEW)}.")

if __name__ == "__main__":
    main()
