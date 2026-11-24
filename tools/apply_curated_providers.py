"""Idempotent: record the intended provider(s) of every curated event_knowledge.json entry.

Content of the entries is NOT changed. Provider names are the runtime provider names Windows writes for these
events (general Windows knowledge, not fetched from a vendor page in this tranche; human verification pending).
KAVT* are Hitachi JP1 message IDs, not Windows events: left without providers (see the reconciliation report).
"""
import json
from pathlib import Path

P = Path("backend/domain/analyzer/services/event_knowledge.json")
SEC = ["Microsoft-Windows-Security-Auditing"]
SCM = ["Service Control Manager"]
PROVIDERS = {
    **{k: SEC for k in ("4624", "4625", "4740", "4720", "4771", "4768", "4672", "4688")},
    **{k: SCM for k in ("7000", "7034", "7009", "7036", "7045")},
    "11": ["Disk"], "51": ["Disk"], "55": ["Ntfs"],
    "1014": ["Microsoft-Windows-DNS-Client"], "1058": ["Microsoft-Windows-GroupPolicy"],
    "134": ["Microsoft-Windows-Time-Service"],
    "5009": ["Microsoft-Windows-WAS"], "5011": ["Microsoft-Windows-WAS"],
    "1000": ["Application Error"], "1001": ["Microsoft-Windows-WER-SystemErrorReporting"],
    "1530": ["Microsoft-Windows-User Profiles Service"], "1511": ["Microsoft-Windows-User Profiles Service"],
    "109": ["Microsoft-Windows-Kernel-Power"], "41": ["Microsoft-Windows-Kernel-Power"],
    "20": ["Microsoft-Windows-WindowsUpdateClient"],
    "1069": ["Microsoft-Windows-FailoverClustering"], "1135": ["Microsoft-Windows-FailoverClustering"],
    "10016": ["Microsoft-Windows-DistributedCOM"],
    "6008": ["EventLog"], "6006": ["EventLog"], "1074": ["User32"],
    "17": ["Microsoft-Windows-WHEA-Logger"],
    "1116": ["Microsoft-Windows-Windows Defender"],
    "1102": ["Microsoft-Windows-Eventlog"],
}


def main():
    raw = P.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    data = json.loads(raw)
    changed = 0
    for key, names in PROVIDERS.items():
        if key not in data:
            raise SystemExit(f"unknown curated id {key}")
        if data[key].get("provider_names") != names:
            data[key] = {"provider_names": names, **{k: v for k, v in data[key].items() if k != "provider_names"}}
            changed += 1
    out = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    P.write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
    print("updated", changed, "of", len(PROVIDERS), "| curated entries without providers:",
          sorted(set(data) - set(PROVIDERS)))


if __name__ == "__main__":
    main()
