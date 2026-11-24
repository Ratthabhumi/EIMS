"""Migrate event_knowledge.json content into the canonical Windows catalog (idempotent, text-level insert).

* Existing catalog records whose curated provider agrees get `diagnostic_guidance.localized_summary` (th/en copied
  verbatim; nothing is deleted from event_knowledge.json).
* Curated entries with no catalog record, or whose provider conflicts with the existing record (1001, 5011), become
  NEW records. Provider-qualified identities use diagnostic_code "<id>:<provider>", so the 163 stable IDs are unchanged.
* Two curated texts contained claims the sources do not support (5011 "hung / failed to ping WAS" is event 5010's
  meaning; 109 "shutdown transition" is narrower than the source's "power-state transition"). They are migrated with
  corrected text and the correction is stated in evidence_basis.
* Nothing is promoted: every record stays operational_context; official_references only where a Microsoft page was seen.
"""
import json
import re
import sys
from pathlib import Path

CAT = Path("backend/domain/analyzer/services/operational_event_catalog.json")
CUR = Path("backend/domain/analyzer/services/event_knowledge.json")
BASIS_CURATED = ("Internal curated summary (event_knowledge.json) migrated verbatim into the canonical catalog on "
                 "2026-11-20. No official source was verified for its wording; human verification pending.")
MSDOC = "https://learn.microsoft.com/"

# (event_id, diagnostic_code or None, title, provider, provider_names, category, severity, description,
#  keywords, official_references, evidence_basis override or None)
NEW = [
    ("11", None, "Disk Controller Error", "Disk", ["Disk"], "Storage", "Error",
     "The Disk driver reported a controller or cable error during an I/O operation on a device.",
     ["disk", "controller error", "cable", "i/o"], [],
     BASIS_CURATED + " A third-party listing describes the event as 'the driver has detected a controller or cable error'."),
    ("17", None, "WHEA-Logger: Corrected Hardware Error", "Microsoft-Windows-WHEA-Logger",
     ["Microsoft-Windows-WHEA-Logger"], "Hardware", "Warning",
     "A corrected hardware error was reported through Windows Hardware Error Architecture (for example PCI Express).",
     ["whea", "corrected hardware error", "pci express"],
     [{"title": "Querying the System Event Log for Hardware Error Events", "url": MSDOC + "windows-hardware/drivers/whea/querying-the-system-event-log-for-hardware-error-events",
       "scope": "Confirms the provider name Microsoft-Windows-WHEA-Logger only; does not describe event 17"}], None),
    ("20", None, "Windows Update Installation Failure", "Microsoft-Windows-WindowsUpdateClient",
     ["Microsoft-Windows-WindowsUpdateClient"], "Windows Update", "Error",
     "Windows Update failed to install an update; the event carries an error code (for example 0x80072efe or 0x80070103).",
     ["windows update", "installation failure", "0x80072efe"], [], BASIS_CURATED),
    ("109", None, "Kernel-Power: Power State Transition", "Microsoft-Windows-Kernel-Power",
     ["Microsoft-Windows-Kernel-Power"], "System", "Info",
     "The kernel power manager started a transition from one power state to another; normal on its own.",
     ["kernel-power", "power state", "shutdown", "sleep"], [],
     "CORRECTED from the curated text, which said 'initiated a shutdown transition'; secondary sources describe a "
     "power-state transition (not only shutdown). No official Microsoft page found; human verification pending."),
    ("134", None, "Time-Service: NTP Synchronisation Problem", "Microsoft-Windows-Time-Service",
     ["Microsoft-Windows-Time-Service"], "Time Synchronisation", "Warning",
     "The Windows Time service could not synchronise with the configured NTP peer.",
     ["time-service", "ntp", "ntpclient", "w32time"], [],
     BASIS_CURATED + " The Event ID to provider mapping could NOT be confirmed from any page found; treat as unverified."),
    ("1069", None, "Cluster Resource Failed", "Microsoft-Windows-FailoverClustering",
     ["Microsoft-Windows-FailoverClustering"], "Clustering", "Error",
     "A clustered resource (for example an IP address, disk or service) failed.",
     ["cluster", "resource failed", "failover"], [],
     BASIS_CURATED + " Only non-Microsoft examples were found for 1069."),
    ("1135", None, "Cluster Node Removed From Membership", "Microsoft-Windows-FailoverClustering",
     ["Microsoft-Windows-FailoverClustering"], "Clustering", "Critical",
     "A cluster node was removed from active membership because it stopped communicating with the other nodes.",
     ["cluster", "node removed", "membership", "heartbeat"],
     [{"title": "Troubleshoot cluster issue with Event ID 1135", "url": "https://support.microsoft.com/kb/3036113",
       "scope": "Event 1135: one or more nodes left the active cluster membership"},
      {"title": "Failover clustering system events", "url": MSDOC + "windows-server/failover-clustering/system-events",
       "scope": "Lists 1135 as EVENT_NODE_DOWN"}], BASIS_CURATED),
    ("1511", None, "Temporary Profile Loaded", "Microsoft-Windows-User Profiles Service",
     ["Microsoft-Windows-User Profiles Service"], "User Profiles", "Warning",
     "Windows could not find or load the user's profile and signed the user in with a temporary profile; changes are lost at logoff.",
     ["user profile", "temporary profile", "1511"],
     [{"title": "User Profiles Service event 1511 (TechNet wiki archive)", "url": MSDOC + "ko-kr/archive/technet-wiki/3571.windows-user-profiles-service-event-1511-windows-cannot-find-the-local-profile-and-is-logging-you-on-with-a-temporary-profile",
       "scope": "Describes event 1511 and its temporary-profile effect (archived page)"}], BASIS_CURATED),
    ("1530", None, "User Registry Handles Leaked", "Microsoft-Windows-User Profiles Service",
     ["Microsoft-Windows-User Profiles Service"], "User Profiles", "Warning",
     "An application left registry handles open when the user profile was unloaded; Windows closed them. By design; usually informational.",
     ["registry handles", "user profile", "1530"],
     [{"title": "Event ID 1530 may be logged in the Application log", "url": "https://support.microsoft.com/en-us/help/947238/event-id-1530-may-be-logged-in-the-application-log-on-a-windows-vista-or-newer-computer",
       "scope": "Event 1530 description"}], BASIS_CURATED),
    ("5009", None, "IIS Application Pool Process Terminated Unexpectedly", "Microsoft-Windows-WAS",
     ["Microsoft-Windows-WAS"], "IIS / Web", "Warning",
     "A worker process serving an IIS application pool terminated unexpectedly (the event records the process ID and exit code).",
     ["iis", "application pool", "was", "w3wp"], [],
     BASIS_CURATED + " The message text matches a third-party reference; no current Microsoft page for 5009 was found."),
    ("5011", "5011:Microsoft-Windows-WAS", "IIS Worker Process Fatal Communication Error (WAS)", "Microsoft-Windows-WAS",
     ["Microsoft-Windows-WAS"], "IIS / Web", "Warning",
     "A process serving an IIS application pool suffered a fatal communication error with the Windows Process Activation Service; Microsoft's guidance treats it as a process-crash indicator.",
     ["iis", "application pool", "was", "w3wp", "fatal communication error"],
     [{"title": "Troubleshoot IIS process termination / crashes", "url": MSDOC + "troubleshoot/developer/webapps/iis/site-behavior-performance/process-termination-crash",
       "scope": "WAS warning 5011 indicates a process crash"}],
     "CORRECTED from the curated text, which described 'hung and failed to ping WAS' (that is a different WAS event). "
     "Wording follows Microsoft's crash guidance; the exact message text can vary by OS version. The existing "
     "catalog record for 5011 is a different provider (Windows Defender)."),
    ("1001", "1001:Microsoft-Windows-WER-SystemErrorReporting", "BugCheck (Blue Screen Recorded After Reboot)",
     "Microsoft-Windows-WER-SystemErrorReporting", ["Microsoft-Windows-WER-SystemErrorReporting"], "System", "Critical",
     "Recorded at the next boot after a bugcheck (blue screen); the existing catalog record for 1001 is Windows Error Reporting (a different provider).",
     ["bugcheck", "bsod", "blue screen", "wer-systemerrorreporting"], [], BASIS_CURATED),
]
OVERRIDE = {
    "5011": {
        "en": {"overview": "Event 5011 (WAS) records that a process serving an IIS application pool suffered a fatal communication error with the Windows Process Activation Service, which indicates the process crashed. The error number in the event data points to the underlying cause.",
               "causes": [], "steps": ["Read the error number in the event data; it differs from the Event ID.",
                                       "Capture a crash dump of the w3wp process with Debug Diagnostics to find why it terminated."]},
        "th": {"overview": "Event 5011 (WAS) บันทึกว่ากระบวนการที่ให้บริการ IIS Application Pool เกิดข้อผิดพลาดร้ายแรงในการสื่อสารกับ Windows Process Activation Service ซึ่งบ่งชี้ว่ากระบวนการล่ม ตัวเลข error ในข้อมูลเหตุการณ์ใช้ชี้สาเหตุเบื้องหลัง",
               "causes": [], "steps": ["ดูหมายเลข error ในข้อมูลเหตุการณ์ (ไม่ใช่ Event ID)",
                                       "เก็บ crash dump ของ w3wp ด้วย Debug Diagnostics เพื่อหาสาเหตุที่กระบวนการหยุดทำงาน"]},
    },
    "109": {
        "en": {"overview": "Event 109 (Kernel-Power) records that the kernel power manager started a transition from one power state to another (for example shutdown, sleep or hibernate). On its own it is normal.",
               "causes": [], "steps": ["Investigate only if the transition was unexpected, repeats, or appears with Event 41 or 6008 around the same time."]},
        "th": {"overview": "Event 109 (Kernel-Power) บันทึกว่าตัวจัดการพลังงานของเคอร์เนลเริ่มเปลี่ยนสถานะพลังงาน (เช่น ปิดเครื่อง สลีป หรือไฮเบอร์เนต) โดยลำพังถือเป็นเหตุการณ์ปกติ",
               "causes": [], "steps": ["ตรวจสอบเมื่อการเปลี่ยนสถานะไม่คาดคิด เกิดซ้ำ หรือเกิดใกล้ Event 41 หรือ 6008"]},
    },
}


def block(obj, indent):
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    return text.replace("\n", "\n" + " " * indent)


def summary(curated_entry, key):
    if key in OVERRIDE:
        return OVERRIDE[key]
    out = {}
    for lang in ("th", "en"):
        body = curated_entry.get(lang)
        if body:
            out[lang] = {"overview": body.get("overview", ""), "causes": body.get("causes", []), "steps": body.get("steps", [])}
    return out


def main():
    text = CAT.read_text(encoding="utf-8")
    crlf = "\r\n" in text
    text = text.replace("\r\n", "\n")
    cur = json.loads(CUR.read_text(encoding="utf-8"))
    records = json.loads(text)
    by_id = {r["event_id"]: r for r in records}
    new_ids = {n[0] for n in NEW}
    conflicts, attached = [], 0

    # 1) existing records whose provider agrees with the curated entry
    lines, out, current = text.split("\n"), [], None
    for line in lines:
        m = re.match(r'\s*"event_id": "([^"]+)"', line)
        if m:
            current = m.group(1)
        if (re.match(r'\s*"source": "OPERATIONAL_EVENT_CATALOG"', line) and current in cur and current not in new_ids
                and "diagnostic_guidance" not in by_id[current]):
            rec = by_id[current]
            names = {n.casefold() for n in cur[current].get("provider_names", [])}
            have = {n.casefold() for n in rec.get("provider_names", [])} | {rec["provider"].casefold()}
            if names and not (names & have):
                conflicts.append((current, rec["provider"], cur[current]["provider_names"]))
            else:
                guidance = {"evidence_basis": BASIS_CURATED, "localized_summary": summary(cur[current], current)}
                out.append('    "diagnostic_guidance": ' + block(guidance, 4) + ",")
                attached += 1
        out.append(line)
    text = "\n".join(out)

    # 2) new records (orphans and provider-qualified)
    existing_codes = {(r["event_id"], r.get("diagnostic_code", r["event_id"])) for r in records}
    blocks = []
    for (eid, code, title, provider, names, category, severity, description, keywords, refs, basis) in NEW:
        if (eid, code or eid) in existing_codes:
            continue
        rec = {"event_id": eid}
        if code:
            rec["diagnostic_code"] = code
        rec.update({"title": title, "provider": provider, "provider_names": names, "category": category,
                    "severity": severity, "description": description, "keywords": keywords, "related_events": [],
                    "operator_context": "Reference material from the migrated curated summary; it describes a symptom and "
                                        "does not by itself establish a root cause.",
                    "official_references": refs,
                    "diagnostic_guidance": {"evidence_basis": basis or BASIS_CURATED, "localized_summary": summary(cur[eid], eid)},
                    "source": "OPERATIONAL_EVENT_CATALOG"})
        blocks.append("  " + block(rec, 2))
    if blocks:
        body = text.rstrip()
        assert body.endswith("]")
        body = body[:-1].rstrip()
        text = body + ",\n" + ",\n".join(blocks) + "\n]\n"
    out_text = text.replace("\n", "\r\n") if crlf else text
    CAT.write_bytes(out_text.encode("utf-8"))
    print(f"attached localized_summary to {attached} existing records; new records: {len(blocks)}; conflicts: {conflicts}")


if __name__ == "__main__":
    sys.exit(main())
