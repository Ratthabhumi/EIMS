import re

from backend.domain.analyzer.schemas.analyze import EventMetadata
from backend.domain.analyzer.services.source_classify import classify_source
from backend.domain.analyzer.services.vendor_parsers import (
    parse_syslog_hinted,
    parse_unknown_text,
    parse_veeam,
    parse_vmware,
)

KNOWN_PROVIDERS = {
    "10016": "DistributedCOM",
    "41": "Kernel-Power",
    "6008": "EventLog",
    "1001": "Windows Error Reporting",
    "4625": "Security",
    "7031": "Service Control Manager",
}

CRITICAL_LEVELS = {"critical", "error", "1", "2", "emergency", "alert"}

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
    has_type = _fortinet_field(text, "type") in ("traffic", "event", "utm", "anomaly", "virus", "webfilter", "ips", "dns")
    return has_type and bool(_fortinet_field(text, "logid") or
        re.search(r"\b(?:fortigate|fortios)\b", text, re.IGNORECASE))


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

    # A deny action is a policy outcome, not proof of a critical incident.
    level_lower = level.lower() if level else ""
    is_critical = (
        level_lower in CRITICAL_LEVELS
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
        diagnosticCode=f"{log_type}/{subtype}" if log_type and subtype else "",
        attributes={"codeType": "log_category", **{
            key: _fortinet_field(text, key) for key in
            ("logid", "type", "subtype", "level", "action", "srcip", "dstip", "service", "policyid", "devname", "msg", "status", "reason")
        }},
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
        diagnosticCode=msg_id if header else "",
        attributes={"codeType": "official_message_id", "deviceType": header.group(1).upper() if header else "",
                    "messageId": msg_id, "severity": severity_num, "message": msg_body},
    )



def is_critical_level(level: str) -> bool:
    normalized = level.strip().lower()
    if not normalized:
        return False
    if normalized in CRITICAL_LEVELS:
        return True
    return "critical" in normalized or normalized == "error"


def _is_json_log(text: str) -> dict | None:
    """Attempts to parse structured JSON log."""
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        try:
            import json
            data = json.loads(stripped)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return data[0]
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def _parse_json_log(data: dict) -> EventMetadata:
    """Extract metadata from standard JSON logs (e.g. Bunyan, Winston, Serilog, Logstash)."""
    event_id = str(data.get("eventId") or data.get("event_id") or data.get("id") or data.get("code") or data.get("status") or "JSON-LOG")
    provider = str(data.get("provider") or data.get("source") or data.get("service") or data.get("app") or data.get("logger") or "Application")
    level = str(data.get("level") or data.get("severity") or data.get("type") or "Info")
    timestamp = str(data.get("timestamp") or data.get("time") or data.get("@timestamp") or data.get("date") or "")
    computer = str(data.get("host") or data.get("hostname") or data.get("server") or data.get("node") or "")
    log_name = str(data.get("message") or data.get("msg") or data.get("error") or data.get("description") or "")
    faulting_app = str(data.get("faultingApp") or data.get("module") or data.get("caller") or "")

    return EventMetadata(
        eventId=event_id,
        provider=provider,
        level=level,
        logName=log_name[:150] if log_name else "JSON Structured Event",
        timestamp=timestamp,
        computer=computer,
        isCritical=is_critical_level(level),
        faultingApp=faulting_app,
    )


_PG_JSONLOG_REQUIRED = {"error_severity", "state_code", "message"}
_PG_JSONLOG_IDENTITY = {"pid", "backend_type", "session_id", "dbname", "line_num"}


def _postgres_jsonlog(data) -> dict:
    """PostgreSQL ``jsonlog`` entry recognised only by its documented keys (PostgreSQL docs, Table "Keys and Values of JSON Log Entries").

    Requires error_severity, state_code and message plus at least one process/session identity key, and a well-formed
    5-character SQLSTATE. Nothing is inferred from message text.
    """
    if not isinstance(data, dict) or not _PG_JSONLOG_REQUIRED <= set(data) or not _PG_JSONLOG_IDENTITY & set(data):
        return {}
    code = str(data.get("state_code") or "")
    if not re.fullmatch(r"[0-9A-Z]{5}", code):
        return {}
    out = {"codeType": "sqlstate", "sqlState": code, "logFormat": "postgresql_jsonlog",
           "pgSeverity": str(data.get("error_severity") or "")}
    if data.get("backend_type"):
        out["pgBackendType"] = str(data["backend_type"])
    return out


def _is_linux_syslog(text: str) -> bool:
    """Detect standard Linux syslog format (e.g., 'Aug 12 10:15:30 server sshd[1234]: Failed password')."""
    pattern = r'^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)\s+([a-zA-Z0-9_\-\.]+)(?:\[\d+\])?:\s*(.*)'
    return bool(re.search(pattern, text.strip(), re.MULTILINE))


# Server messages whose exact wording is confirmed by the PostgreSQL 16 documentation (Routine Vacuuming, "Preventing
# Transaction ID Wraparound Failures") or by the upstream REL_16_STABLE source (checkpointer.c, shell_archive.c, pgarch.c,
# tcop/postgres.c). Recognised only on syslog-forwarded lines whose program is postgres* (log_destination=syslog,
# default syslog_ident "postgres"); nothing is inferred from other wording.
_PG_DOCUMENTED_MESSAGES = {
    "pg_xid_wraparound_warning": re.compile(r'WARNING:\s+database "(?P<database>[^"]+)" must be vacuumed within (?P<transactions>\d+) transactions'),
    "pg_xid_wraparound_refusal": re.compile(r'ERROR:\s+database is not accepting commands to avoid wraparound data loss in database "(?P<database>[^"]+)"'),
    "pg_checkpoint_too_frequent": re.compile(r'checkpoints are occurring too frequently \((?P<seconds>\d+) seconds? apart\)'),
    "pg_archive_command_failed": re.compile(r'archive command failed with exit code (?P<exitCode>\d+)'),
    "pg_archive_failed_too_many_times": re.compile(r'archiving write-ahead log file "(?P<walFile>[^"]+)" failed too many times, will try again later'),
    "pg_recovery_conflict_cancel": re.compile(r'canceling statement due to conflict with recovery'),
    "pg_recovery_conflict_terminate": re.compile(r'terminating connection due to conflict with recovery'),
}
PG_DOCUMENTED_MESSAGE_KEYS = frozenset(_PG_DOCUMENTED_MESSAGES)


def _postgres_documented_message(daemon: str, msg: str) -> dict:
    if not daemon.lower().startswith("postgres"):
        return {}
    for key, pattern in _PG_DOCUMENTED_MESSAGES.items():
        m = pattern.search(msg)
        if m:
            return {"messageKey": key, "product": "PostgreSQL", **{k: v for k, v in m.groupdict().items() if v}}
    return {}


_SYSTEMD_EXIT = re.compile(
    r"^(?:(?P<unit>[^\s:]+\.(?:service|socket|mount|swap|timer|target|path|scope|slice)):\s+)?"
    r"(?P<kind>Main process|Control process|\S+(?: \S+)? process) exited, code=exited, status=(?P<status>\d{1,3})/(?P<name>[A-Z0-9_]+)",
)


def _systemd_exit_status(daemon: str, msg: str) -> dict:
    """Exit status explicitly printed by systemd for a process that exited on its own (never inferred).

    Signal terminations (code=killed/dumped) are not exit statuses and are not matched.
    """
    if daemon != "systemd":
        return {}
    m = _SYSTEMD_EXIT.match(msg.strip())
    if not m or m.group("status") == "0":
        return {}
    out = {"exitStatus": m.group("status"), "exitName": m.group("name"), "processKind": m.group("kind")}
    if m.group("unit"):
        out["unit"] = m.group("unit")
    return out


def _parse_linux_syslog(text: str) -> EventMetadata:
    """Parse standard Linux Syslog / auth.log / kern.log format."""
    pattern = r'([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+([a-zA-Z0-9_\-\.]+)(?:\[\d+\])?:\s*(.*)'
    match = re.search(pattern, text.strip())
    if match:
        timestamp, computer, daemon, msg = match.groups()
        
        # Determine event id and level based on message
        msg_lower = msg.lower()
        level = "Error" if any(k in msg_lower for k in ("fail", "error", "corrupt", "panic", "segfault", "fatal", "denied")) else "Information"
        
        # Identify common Linux daemon events
        event_id = "SYSLOG"
        if daemon == "sshd" and "failed password" in msg_lower:
            event_id = "AUTH-FAIL"
            level = "Error"
        elif "segfault" in msg_lower:
            event_id = "SIGSEGV"
            level = "Critical"
        elif "kernel panic" in msg_lower:
            event_id = "PANIC"
            level = "Emergency"
        elif "connection refused" in msg_lower:
            event_id = "CONN-REFUSED"
            
        attributes = {"codeType": "general_signature", "daemon": daemon, "message": msg}
        pg_message = _postgres_documented_message(daemon, msg)
        if pg_message:
            attributes.update(pg_message, codeType="documented_message")
        exit_status = _systemd_exit_status(daemon, msg)
        if exit_status:
            # Documented systemd message "<kind> exited, code=exited, status=<N>/<NAME>" (src/core/unit.c).
            attributes.update(exit_status, codeType="process_exit_status")
        return EventMetadata(
            eventId=event_id,
            provider=f"Linux/{daemon}",
            level=level,
            logName=msg[:150],
            timestamp=timestamp,
            computer=computer,
            isCritical=is_critical_level(level),
            faultingApp=daemon,
            diagnosticCode=event_id if event_id == "AUTH-FAIL" else "",
            attributes=attributes,
        )
    return EventMetadata(eventId="Linux-Syslog", provider="Linux/System", level="Info")


def _stamp(meta: EventMetadata, family: str, product: str, confidence: float) -> EventMetadata:
    """Attach source-aware identity without changing parsed field behavior."""
    meta.sourceFamily = family
    meta.product = product
    meta.parserConfidence = confidence
    return meta


def parse_event_metadata(text: str, filename_hint: str = "") -> EventMetadata:
    if not text:
        return EventMetadata(sourceFamily="unknown_text", parserConfidence=0.3)

    classification = classify_source(text, filename_hint)
    family = str(classification.get("sourceFamily") or "unknown_text")
    confidence = float(classification.get("parserConfidence") or 0.0)

    # 1. Structured JSON logs keep their dedicated parser.
    json_data = _is_json_log(text)
    if json_data:
        meta = _stamp(_parse_json_log(json_data), "json", "JSON structured log", max(confidence, 0.85))
        pg = _postgres_jsonlog(json_data)
        if pg:  # explicit PostgreSQL jsonlog keys; the family stays "json" (no new source family)
            meta.attributes = {**(meta.attributes or {}), **pg}
            meta.provider = "PostgreSQL"
        return _merge_syslog(meta, text, family)

    # 2. Veeam / VMware vendor adapters (deterministic, stdlib only).
    if family == "veeam_vbr":
        return _merge_syslog(parse_veeam(text, filename_hint), text, family)
    if family == "vmware":
        return _merge_syslog(parse_vmware(text, filename_hint), text, family)
    if family == "palo_alto":
        from backend.domain.analyzer.services.panos_parser import parse_panos
        return parse_panos(text) or parse_unknown_text(text, filename_hint)

    # 3. Fortinet / Cisco / Linux keep their dedicated parsers.
    if family == "fortinet":
        return _merge_syslog(_stamp(_parse_fortinet(text), "fortinet", "Fortinet FortiGate", max(confidence, 0.85)), text, family)
    if family == "cisco_asa":
        return _merge_syslog(_stamp(_parse_cisco_asa(text), "cisco_asa", "Cisco ASA/FTD", max(confidence, 0.85)), text, family)
    if family == "linux_syslog":
        return _merge_syslog(_stamp(_parse_linux_syslog(text), "linux_syslog", "Linux syslog", max(confidence, 0.85)), text, family)

    # 4. Windows parsing requires positive Windows evidence.  Anything else
    #    is unknown_text and MUST NOT fall through to Windows regex.
    if family != "windows_event":
        return parse_unknown_text(text, filename_hint)

    return _stamp(_parse_windows(text), "windows_event", "Microsoft Windows", max(confidence, 0.8))


def _merge_syslog(meta: EventMetadata, text: str, family: str) -> EventMetadata:
    """Attach RFC 5424 structured data (Veeam_MP) to vendor metadata.

    Raw session/instance IDs remain in the persisted attributes only; they
    are never embedded (vector_db redacts session ids) and never become the
    Windows Event ID.
    """
    try:
        syslog = parse_syslog_hinted(text, family)
    except Exception:
        syslog = None
    if syslog:
        attrs = dict(meta.attributes or {})
        attrs["syslog"] = {k: v for k, v in syslog.items() if k != "sourceFamily"}
        meta.attributes = attrs
    return meta


def windows_group_policy_connectivity(event_id: str, provider: str, text: str) -> bool:
    """Classify the reported symptom, never its physical cause or job outcome."""
    identity = provider.lower().replace('-', '').replace(' ', '')
    message = (_field(text, r"(?m)^\s*Description\s*:\s*([^\r\n]+)") or text).lower()
    return bool(
        event_id == "1129" and identity in {"microsoftwindowsgrouppolicy", "grouppolicy"}
        and 'domain controller' in message
        and any(s in message for s in ('could not contact', 'lack of network connectivity', 'connectivity failed'))
    )


_MAX_STACK_FRAMES = 40


def _windows_attributes(text: str) -> tuple[str, dict]:
    """Source identity and .NET runtime details that are stated verbatim in the text (never inferred).

    Returns (application, attributes). ``recordId`` feeds Incident Core's evidence identity; the stack trace is kept
    as written (first block, bounded) so the engineer can read it without it being summarised into a cause.
    """
    attrs: dict = {}
    record = _field(text, r"(?i)Event\s*Record\s*ID\s*[:=]\s*(\d+)", r"(?i)<EventRecordID>\s*(\d+)\s*</EventRecordID>")
    if record:
        attrs["recordId"] = record
    framework = _field(text, r"(?im)^\s*Framework\s+Version\s*:\s*([^\r\n]+)")
    application = ""
    if framework:
        attrs["frameworkVersion"] = framework.strip()
        application = (_field(text, r"(?im)^\s*Application\s*:\s*([^\r\n]+)") or "").strip()
        if application:
            attrs["application"] = application
    lines = (text or "").splitlines()
    starts = [i for i, ln in enumerate(lines) if re.match(r"\s*Exception\s+Info\s*:", ln, re.I)]
    if starts:
        first = starts[0]
        attrs["exceptionInfo"] = lines[first].split(":", 1)[1].strip()[:300]
        frames = []
        for ln in lines[first + 1:]:
            if re.match(r"\s+at\s+\S", ln):
                frames.append(ln.strip()[:300])
            else:
                break
        attrs["stackFrames"] = frames[:_MAX_STACK_FRAMES]
        attrs["exceptionBlockCount"] = len(starts)
    return application, attrs


def _windows_event_xml(text: str) -> dict:
    """Structured fields from a pasted Windows Event XML (Event Viewer "XML View").

    ``TimeCreated/@SystemTime`` is the structured, zone-qualified (UTC) time the event was logged, so it is preferred over
    any free-text date. Parsed with defusedxml; anything that is not a well-formed single <Event> yields nothing.
    """
    stripped = text.strip()
    if "<Event" not in stripped or "<System" not in stripped:
        return {}
    start = stripped.find("<Event")
    try:
        from defusedxml import ElementTree as SafeET

        root = SafeET.fromstring(stripped[start:stripped.rfind("</Event>") + len("</Event>")].encode("utf-8"))
    except Exception:  # noqa: BLE001 - malformed/hostile XML: fall back to the text parser, never fail the request
        return {}

    def local(tag):
        return tag.rsplit("}", 1)[-1]

    system = next((child for child in root if local(child.tag) == "System"), None)
    if system is None:
        return {}
    found: dict = {}
    for child in system:
        name = local(child.tag)
        if name == "Provider":
            found["provider"] = (child.get("Name") or "").strip()
        elif name == "EventID":
            found["event_id"] = (child.text or "").strip()
        elif name == "TimeCreated":
            found["timestamp"] = (child.get("SystemTime") or "").strip()
        elif name == "Computer":
            found["computer"] = (child.text or "").strip()
        elif name == "Channel":
            found["log_name"] = (child.text or "").strip()
        elif name == "EventRecordID":
            found["record_id"] = (child.text or "").strip()
        elif name == "Level":
            found["level"] = {"1": "Critical", "2": "Error", "3": "Warning", "4": "Information", "5": "Verbose"}.get(
                (child.text or "").strip(), (child.text or "").strip())
    return found


def _parse_windows(text: str) -> EventMetadata:
    """Windows fields plus a narrowly supported Group Policy symptom category."""
    xml = _windows_event_xml(text)
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
    
    if xml:  # structured values win over free-text guesses
        event_id = xml.get("event_id") or event_id
        provider = xml.get("provider") or provider
        level = xml.get("level") or level
        log_name = xml.get("log_name") or log_name
        timestamp = xml.get("timestamp") or timestamp
        computer = xml.get("computer") or computer

    # Extract faulting application name
    faulting_app = _field(
        text,
        r"Faulting\s+application\s+name[:\s]+([^\n\r]+)",
        r"Faulting\s+module\s+name[:\s]+([^\n\r]+)",
    )

    runtime_app, extra_attributes = _windows_attributes(text)
    if xml.get("timestamp"):
        extra_attributes = {**(extra_attributes or {}), "timeSource": "xml:System/TimeCreated@SystemTime"}
    if xml.get("record_id"):
        extra_attributes = {**(extra_attributes or {}), "recordId": xml["record_id"]}
    return EventMetadata(
        eventId=event_id or "Unknown",
        provider=provider or "Unknown",
        level=level,
        logName=log_name,
        timestamp=timestamp,
        computer=computer,
        isCritical=is_critical_level(level),
        faultingApp=faulting_app or runtime_app,
        attributes=extra_attributes,
        diagnosticCode=("WINDOWS-GROUP-POLICY-CONNECTIVITY"
                        if windows_group_policy_connectivity(event_id, provider, text)
                        and re.search(r"(?im)^\s*Event\s*ID\s*:\s*1129\s*$", text)
                        and re.search(r"(?im)^\s*(?:Source|Provider(?:\s+Name)?)\s*:", text)
                        else ""),
    )
