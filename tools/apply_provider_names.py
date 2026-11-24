"""Idempotent: add verified-by-convention `provider_names` to selected Windows records (text insert, no reformatting).

Stable catalog IDs are untouched. Names are the runtime provider names Windows writes for these events; they were
NOT fetched from a vendor page in this tranche, so human verification is recorded as pending in the report.
"""
import json
import re
from pathlib import Path

P = Path("backend/domain/analyzer/services/operational_event_catalog.json")
SEC = "Microsoft-Windows-Security-Auditing"
NAMES = {
    "1000": ["Application Error"], "1001": ["Windows Error Reporting"], "1002": ["Application Hang"],
    "1026": [".NET Runtime"],
    "41": ["Microsoft-Windows-Kernel-Power"], "1074": ["User32"], "1076": ["User32"],
    "6005": ["EventLog"], "6006": ["EventLog"], "6008": ["EventLog"], "6013": ["EventLog"],
    "1102": ["Microsoft-Windows-Eventlog"], "1104": ["Microsoft-Windows-Eventlog"],
    "1014": ["Microsoft-Windows-DNS-Client"], "1015": ["Microsoft-Windows-DNS-Client"],
}
for code in ("4624 4625 4634 4647 4648 4672 4688 4689 4697 4704 4705 4720 4722 4723 4724 4725 4726 4728 4729 4732 4733 "
             "4735 4737 4738 4740 4741 4742 4743 4767 4768 4769 4771 4776 4781 4662 5136 5137 5138 5140 5142 5143 5144 "
             "5145 4698 4699 4700 4701 4702 5152 5155 5156 5157 5158 5159").split():
    NAMES[code] = [SEC]


for code in "1116 1117 1118 1119 1121 1122 1150 2001 3002 5001 5007 5010 5011".split():
    NAMES[code] = ["Microsoft-Windows-Windows Defender"]


def main():
    lines = P.read_text(encoding="utf-8").split("\n")
    out, current, done = [], None, 0
    for i, line in enumerate(lines):
        out.append(line)
        m = re.match(r'\s*"event_id": "([^"]+)"', line)
        if m:
            current = m.group(1)
        if current in NAMES and re.match(r'\s*"provider": ', line):
            if not any('"provider_names"' in l for l in lines[i + 1:i + 3]):
                indent = re.match(r"\s*", line).group(0)
                out.append(f'{indent}"provider_names": {json.dumps(NAMES[current], ensure_ascii=False)},')
                done += 1
    P.write_text("\n".join(out), encoding="utf-8", newline="")
    print("inserted", done, "of", len(NAMES))


if __name__ == "__main__":
    main()
