import re

from app.schemas.analyze import EventMetadata

KNOWN_PROVIDERS = {
    "10016": "DistributedCOM",
    "41": "Kernel-Power",
    "6008": "EventLog",
    "1001": "Windows Error Reporting",
    "4625": "Security",
    "7031": "Service Control Manager",
}

CRITICAL_LEVELS = {"critical", "error", "1", "2", "emergency", "alert"}

# Fortinet log action types that are security-relevant
FORTINET_CRITICAL_ACTIONS = {"block", "deny", "drop", "reset", "blocked"}

# Cisco ASA severity levels (0=emergency, 1=alert, 2=critical, 3=error, 4=warning)
CISCO_CRITICAL_SEVERITIES = {0, 1, 2, 3}


def _field(text: str, *patterns: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _fortinet_field(text: str, key: str) -> str:
    """Extract key=value or key="value" from Fortinet log line."""
    match = re.search(rf'(?:^|\s){re.escape(key)}="([^"]*)"', text)
    if match:
        return match.group(1).strip()
    match = re.search(rf'(?:^|\s){re.escape(key)}=(\S+)', text)
    if match:
        return match.group(1).strip()
    return ""


def _is_fortinet_log(text: str) -> bool:
    """Detect if text looks like a Fortinet/FortiGate log."""
    fortinet_markers = [
        r'devname=',
        r'logid=',
        r'type="(traffic|event|utm|anomaly|virus|webfilter|ips|dns)"',
        r'fortigate',
        r'fortios',
        r'fgt_',
        r'subtype="(forward|local|ips|webfilter|antivirus)"',
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in fortinet_markers)


def _parse_fortinet(text: str) -> EventMetadata:
    """Parse Fortinet FortiGate log format."""
    log_id  = _fortinet_field(text, "logid")
    log_type = _fortinet_field(text, "type")
    subtype  = _fortinet_field(text, "subtype")
    level    = _fortinet_field(text, "level") or _fortinet_field(text, "severity")
    action   = _fortinet_field(text, "action")
    devname  = _fortinet_field(text, "devname")
    srcip    = _fortinet_field(text, "srcip")
    dstip    = _fortinet_field(text, "dstip")
    service  = _fortinet_field(text, "service")
    msg      = _fortinet_field(text, "msg")
    policyid = _fortinet_field(text, "policyid")

    # Build a human-readable event ID: logid or type+subtype
    event_id = log_id if log_id else f"{log_type}-{subtype}" if log_type else "Fortinet"
    provider = f"FortiGate/{log_type}" if log_type else "FortiGate"
    if subtype:
        provider += f"/{subtype}"

    # Timestamp: date= + time=
    date_v = _fortinet_field(text, "date")
    time_v = _fortinet_field(text, "time")
    timestamp = f"{date_v} {time_v}".strip() if date_v or time_v else ""

    # Build description
    parts = []
    if srcip:   parts.append(f"Src: {srcip}")
    if dstip:   parts.append(f"Dst: {dstip}")
    if service: parts.append(f"Service: {service}")
    if action:  parts.append(f"Action: {action}")
    if policyid: parts.append(f"PolicyID: {policyid}")
    if msg:     parts.append(f"Message: {msg}")
    log_name = " | ".join(parts) if parts else log_type

    # Critical if action is block/deny/drop or level is emergency/alert/error
    level_lower = level.lower() if level else ""
    action_lower = action.lower() if action else ""
    is_critical = (
        level_lower in CRITICAL_LEVELS
        or action_lower in FORTINET_CRITICAL_ACTIONS
    )

    return EventMetadata(
        eventId=event_id or "Unknown",
        provider=provider,
        level=level or action or "",
        logName=log_name,
        timestamp=timestamp,
        computer=devname,
        isCritical=is_critical,
        faultingApp="",
    )

def _is_cisco_asa(text: str) -> bool:
    """Detect Cisco ASA / FTD log format."""
    patterns = [
        r'%ASA-\d+-\d+',
        r'%FTD-\d+-\d+',
        r'%PIX-\d+-\d+',
        r'Cisco Adaptive Security',
        r'ASA\d{4}',  # device name like ASA5506
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


# Cisco ASA message IDs and their human-readable names
CISCO_MSG_NAMES = {
    "106001": "Inbound TCP denied",
    "106006": "Deny inbound packet",
    "106007": "Deny inbound UDP",
    "106014": "Deny inbound ICMP",
    "106023": "Deny TCP/UDP/ICMP packet",
    "106100": "Access-list permit/deny",
    "302013": "TCP connection built",
    "302014": "TCP connection torn down",
    "302015": "UDP connection built",
    "302016": "UDP connection torn down",
    "302020": "ICMP connection built",
    "305011": "NAT translation built",
    "305012": "NAT translation torn down",
    "402117": "IPSEC crypto map failed",
    "402119": "IPSEC packet error",
    "500004": "Invalid transport field",
    "710003": "Connection to interface denied",
    "733100": "Object drop rate exceeded",
}


def _parse_cisco_asa(text: str) -> EventMetadata:
    """Parse Cisco ASA/FTD/PIX syslog format."""
    # Match: %ASA-severity-msgid or %FTD-severity-msgid
    header = re.search(
        r'%(ASA|FTD|PIX)-(\d)-(\d+):?\s*(.*)',
        text, re.IGNORECASE | re.DOTALL
    )

    device_type = "Cisco ASA"
    severity_num = 5  # default: notification
    msg_id = "Unknown"
    msg_body = text

    if header:
        device_type = f"Cisco {header.group(1).upper()}"
        severity_num = int(header.group(2))
        msg_id = header.group(3)
        msg_body = header.group(4).strip()

    # Map severity number to level name
    severity_map = {
        0: "Emergency", 1: "Alert", 2: "Critical",
        3: "Error", 4: "Warning", 5: "Notification",
        6: "Informational", 7: "Debug"
    }
    level = severity_map.get(severity_num, "Notification")

    # Get human-readable name for message ID
    msg_name = CISCO_MSG_NAMES.get(msg_id, "")
    provider = f"{device_type}/{msg_name}" if msg_name else device_type

    # Extract source/destination from message body
    src = re.search(r'src\s+\w+:([\d./]+)', msg_body, re.IGNORECASE)
    dst = re.search(r'dst\s+\w+:([\d./]+)', msg_body, re.IGNORECASE)
    src_ip = src.group(1) if src else ""
    dst_ip = dst.group(1) if dst else ""

    # Extract timestamp from syslog header
    ts_match = re.search(
        r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\s+\d{4})?)',
        text
    )
    timestamp = ts_match.group(1) if ts_match else ""

    # Extract hostname/device from syslog
    host_match = re.search(
        r'(?:^|>)\s*(\S+)\s+%(?:ASA|FTD|PIX)',
        text, re.IGNORECASE
    )
    computer = host_match.group(1) if host_match else ""

    # Build log_name from key fields
    parts = []
    if src_ip: parts.append(f"Src: {src_ip}")
    if dst_ip: parts.append(f"Dst: {dst_ip}")
    if msg_body and not src_ip:
        parts.append(msg_body[:120])
    log_name = " | ".join(parts) if parts else msg_name

    is_critical = severity_num in CISCO_CRITICAL_SEVERITIES

    return EventMetadata(
        eventId=msg_id,
        provider=provider,
        level=level,
        logName=log_name,
        timestamp=timestamp,
        computer=computer,
        isCritical=is_critical,
        faultingApp="",
    )



def is_critical_level(level: str) -> bool:
    normalized = level.strip().lower()
    if not normalized:
        return False
    if normalized in CRITICAL_LEVELS:
        return True
    return "critical" in normalized or normalized == "error"


def parse_event_metadata(text: str) -> EventMetadata:
    if not text:
        return EventMetadata()

    # Detect Fortinet log first
    if _is_fortinet_log(text):
        return _parse_fortinet(text)

    # Detect Cisco ASA/FTD
    if _is_cisco_asa(text):
        return _parse_cisco_asa(text)

    event_id = _field(text, r"Event\s*ID[:\s]+(\d+)", r'"id"[:\s]+(\d+)', r"'id'[:\s]+(\d+)")
    provider = _field(
        text,
        r"Provider\s*Name[:\s]+([^\n\r]+)",
        r"Source[:\s]+([^\n\r]+)",
        r"Provider[:\s]+([^\n\r]+)",
        r'"provider"[:\s]+"([^"]+)"',
        r"'provider'[:\s]+'([^']+)'",
    )
    if not provider and event_id in KNOWN_PROVIDERS:
        provider = KNOWN_PROVIDERS[event_id]

    level = _field(text, r"Level[:\s]+([^\n\r]+)")
    log_name = _field(text, r"Log\s*Name[:\s]+([^\n\r]+)")
    timestamp = _field(
        text,
        r"Date\s*(?:and\s*Time)?[:\s]+([^\n\r]+)",
        r"Time\s*Created[:\s]+([^\n\r]+)",
        r"Logged[:\s]+([^\n\r]+)",
    )
    computer = _field(text, r"Computer[:\s]+([^\n\r]+)")
    
    # Extract faulting application name
    faulting_app = _field(
        text,
        r"Faulting\s+application\s+name[:\s]+([^\n\r]+)",
        r"Faulting\s+module\s+name[:\s]+([^\n\r]+)",
    )

    return EventMetadata(
        eventId=event_id or "Unknown",
        provider=provider or "Unknown",
        level=level,
        logName=log_name,
        timestamp=timestamp,
        computer=computer,
        isCritical=is_critical_level(level),
        faultingApp=faulting_app,
    )
