"""PAN-OS default CSV syslog core fields, not custom/GUI/CEF/LEEF formats.

Field order verified against official Traffic, Threat, System and Config
Log Fields. CONFIG before/after details are custom-only and are excluded.
Require the documented header, serial and valid receive/generated times.
Reject heterogeneous input rather than choose an arbitrary first record.
"""
import csv
import io
import re
from datetime import datetime
from ipaddress import ip_address

from backend.domain.analyzer.schemas.analyze import EventMetadata

_START = re.compile(r'(?:^|\s)([01],\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2},)')
_SEVERITIES = {"informational", "info", "low", "medium", "high", "critical"}
_MIN_FIELDS = {"TRAFFIC": 31, "THREAT": 35, "SYSTEM": 15, "CONFIG": 14}


def _timestamp(value):
    try:
        datetime.strptime(value, "%Y/%m/%d %H:%M:%S")
        return True
    except ValueError:
        return False


def panos_records(text: str) -> list[tuple[int, list[str], str]]:
    records = []
    for line_number, raw in enumerate((text or "").splitlines(), 1):
        if not raw.strip():
            continue
        match = _START.search(raw)
        if not match:
            return []
        try:
            fields = next(csv.reader(io.StringIO(raw[match.start(1):]), strict=True))
        except (csv.Error, StopIteration):
            return []
        if len(fields) < 7:
            return []
        typ = fields[3]
        if typ not in _MIN_FIELDS or len(fields) < _MIN_FIELDS[typ]:
            return []
        if not _timestamp(fields[1]) or not _timestamp(fields[6]) or not re.fullmatch(r"\d{6,20}", fields[2]):
            return []
        if typ in ("TRAFFIC", "THREAT"):
            try:
                ip_address(fields[7])
                ip_address(fields[8])
            except ValueError:
                return []
            if not fields[4] or not fields[30]:
                return []
        if typ in ("SYSTEM", "THREAT") and fields[13 if typ == "SYSTEM" else 34].lower() not in _SEVERITIES:
            return []
        if typ == "CONFIG" and fields[12] not in ("Submitted", "Succeeded", "Failed", "Unauthorized"):
            return []
        records.append((line_number, fields, raw))
    return records


def parse_panos(text: str) -> EventMetadata | None:
    records = panos_records(text)
    if not records:
        return None
    line_number, f, raw = records[0]
    typ = f[3]
    attrs = dict(type=typ, subtype=f[4], serial=f[2], receiveTime=f[1], generatedTime=f[6],
                 timezoneUncertainty="Default timestamps contain no timezone offset",
                 codeType="log_category", format="panos_default_csv", lineNumber=line_number,
                 raw=raw, recordCount=len(records))
    level, action, description, event_id = "Informational", "", "", typ
    if typ in ("TRAFFIC", "THREAT"):
        attrs.update(srcip=f[7], dstip=f[8], rule=f[11], application=f[14], action=f[30])
        action = f[30]
        description = f"{attrs['srcip']} -> {attrs['dstip']}; {attrs['application']}; {action}"
        if typ == "THREAT":
            level = f[34]
            attrs.update(threatId=f[32], description=f[31])
            event_id = f[32] or typ
        device_index = 52 if typ == "TRAFFIC" else 59
    elif typ == "SYSTEM":
        event_id, level, description = f[8] or typ, f[13], f[14]
        attrs.update(eventId=f[8], module=f[12], description=description)
        device_index = 22
    else:
        action, description = f[9], f[13]
        attrs.update(host=f[7], command=f[9], admin=f[10], client=f[11], result=f[12], path=f[13])
        # Only the common CONFIG core is consumed; optional/custom tails
        # cannot shift trusted administrative fields.
        device_index = None
    computer = f[device_index] if device_index is not None and len(f) > device_index else f[2]
    return EventMetadata(eventId=event_id, provider=f"PAN-OS/{typ}/{f[4]}",
                         level=level, logName=description, timestamp=f[6], computer=computer,
                         isCritical=level.lower() in ("high", "critical"),
                         sourceFamily="palo_alto", product="Palo Alto Networks PAN-OS",
                         diagnosticCode=typ, parserConfidence=0.9, attributes=attrs)
