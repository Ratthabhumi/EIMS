import re
from pathlib import Path
from tempfile import TemporaryDirectory
from collections.abc import Generator
from typing import Any
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

LEVEL_MAP = {
    "0": "LogAlways",
    "1": "Critical",
    "2": "Error",
    "3": "Warning",
    "4": "Information",
    "5": "Verbose",
}
AUDIT_FAILURE_KEYWORD = 0x10000000000000
AUDIT_SUCCESS_KEYWORD = 0x20000000000000


def _text(elem: Element | None) -> str:
    return (elem.text or "").strip() if elem is not None else ""


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


_MAX_USER_DATA_DEPTH = 32  # deterministic bound; well below recursion and JSON-encoder limits
_ASCII_DECIMAL = re.compile(r"[0-9]{1,10}")
# Canonical keys derived by the parser; EventData must never be able to set them directly.
_RESERVED_METADATA_KEYS = frozenset({"target_user_name", "workstation_name", "source_network_ip"})


def _is_reserved_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("evtx_") or lowered in _RESERVED_METADATA_KEYS


def _element_value(elem: Element, parent_ns: str, depth: int = 0) -> Any:
    """Lossless nested form: attributes as '@name', repeated children as lists, mixed text as '#text'."""
    if depth > _MAX_USER_DATA_DEPTH:
        raise ValueError("user-data-too-deep")
    ns = _namespace(elem.tag)
    children = list(elem)
    if not children and not elem.attrib and ns == parent_ns:
        return _text(elem)
    value: dict[str, Any] = {f"@{key.rsplit('}', 1)[-1]}": val for key, val in elem.attrib.items()}
    if ns != parent_ns:
        value["@xmlns"] = ns
    if _text(elem) or not children:
        value["#text"] = _text(elem)
    repeated: set[str] = set()
    for child in children:
        name, item = child.tag.rsplit("}", 1)[-1], _element_value(child, ns, depth + 1)
        if name not in value:
            value[name] = item
        elif name in repeated:
            value[name].append(item)
        else:
            value[name] = [value[name], item]
            repeated.add(name)
    return value


def parse_evtx_records(content: bytes) -> Generator[dict[str, Any], None, None]:
    """
    Parses a raw Windows .evtx binary file and yields structured dictionary
    records matching the EIMS WindowsEventLog payload schema.

    Exactly one item is yielded per EVTX record so positions stay stable for
    idempotency keys; unusable records yield {"parse_error": <reason>}.
    Missing TimeCreated is yielded as "" (never fabricated) and fails validation downstream.
    """
    try:
        from Evtx.Evtx import Evtx
    except ImportError:
        raise RuntimeError("python-evtx is not installed.")

    # python-evtx opens a filesystem path (not a BytesIO object). Keep the
    # temporary file alive for the entire generator lifetime, then remove it.
    with TemporaryDirectory(prefix="eims-evtx-") as temp_dir:
        source_path = Path(temp_dir) / "input.evtx"
        source_path.write_bytes(content)
        with Evtx(str(source_path)) as log:
            try:
                record_iter = iter(log.records())
            except Exception as exc:
                yield {"parse_error": f"iteration-failed:{type(exc).__name__}"}
                return
            while True:
                # An exception from the underlying iterator must not discard records already
                # yielded: emit one sentinel at the next stable position, then stop (a failed
                # generator cannot be resumed).
                try:
                    record = next(record_iter)
                except StopIteration:
                    break
                except Exception as exc:
                    yield {"parse_error": f"iteration-failed:{type(exc).__name__}"}
                    break
                try:
                    root = ET.fromstring(record.xml())
                except ET.ParseError:
                    yield {"parse_error": "xml-parse-error"}
                    continue
                except Exception as exc:
                    yield {"parse_error": f"record-unreadable:{type(exc).__name__}"}
                    continue

                system = root.find("e:System", NS)
                if system is None:
                    yield {"parse_error": "missing-system"}
                    continue

                event_id_str = _text(system.find("e:EventID", NS))
                # ASCII decimal only: str.isdigit()/int() also accept Unicode digits and '²'.
                if not _ASCII_DECIMAL.fullmatch(event_id_str):
                    yield {"parse_error": "invalid-event-id"}
                    continue

                event_id = int(event_id_str)
                level_raw = _text(system.find("e:Level", NS))
                level = LEVEL_MAP.get(level_raw, "Unknown")
                channel = _text(system.find("e:Channel", NS))

                time_elem = system.find("e:TimeCreated", NS)
                timestamp = (time_elem.get("SystemTime") or "").strip() if time_elem is not None else ""

                # Extract EventData as metadata
                metadata: dict[str, Any] = {"evtx_level": level_raw}
                keywords = _text(system.find("e:Keywords", NS))
                if keywords:
                    metadata["evtx_keywords"] = keywords
                    try:
                        mask = int(keywords, 16)
                    except ValueError:
                        mask = 0
                    if mask & AUDIT_FAILURE_KEYWORD:
                        metadata["evtx_audit_result"] = "Audit Failure"
                    elif mask & AUDIT_SUCCESS_KEYWORD:
                        metadata["evtx_audit_result"] = "Audit Success"

                # System metadata under namespaced keys (EventData cannot reach these names).
                provider = system.find("e:Provider", NS)
                provider_name = (provider.get("Name") or "").strip() if provider is not None else ""
                if provider_name:
                    metadata["evtx_provider_name"] = provider_name
                computer = _text(system.find("e:Computer", NS))
                if computer:
                    metadata["evtx_computer"] = computer
                record_id = _text(system.find("e:EventRecordID", NS))
                if record_id:
                    metadata["evtx_event_record_id"] = record_id
                execution = system.find("e:Execution", NS)
                if execution is not None:
                    exec_attrs = {k: v for k in ("ProcessID", "ThreadID")
                                  if (v := (execution.get(k) or "").strip())}
                    if exec_attrs:
                        metadata["evtx_execution"] = exec_attrs
                security = system.find("e:Security", NS)
                security_user_id = (security.get("UserID") or "").strip() if security is not None else ""
                if security_user_id:
                    metadata["evtx_security_user_id"] = security_user_id

                named: dict[str, str] = {}
                conflicts: dict[str, list[str]] = {}
                event_data = root.find("e:EventData", NS)
                if event_data is not None:
                    unnamed = []
                    for data in event_data.findall("e:Data", NS):
                        name = data.get("Name", "")
                        if not name:
                            unnamed.append(_text(data))
                        elif _is_reserved_name(name) or name in named:
                            # Reserved parser keys and repeated Names are preserved, never overwritten.
                            conflicts.setdefault(name, []).append(_text(data))
                        else:
                            named[name] = _text(data)
                    if unnamed:
                        metadata["evtx_event_data_values"] = unnamed
                    if conflicts:
                        metadata["evtx_event_data_conflicts"] = conflicts
                user_data = root.find("e:UserData", NS)
                if user_data is not None and len(user_data):
                    try:
                        metadata["evtx_user_data"] = _element_value(user_data, _namespace(user_data.tag))
                    except Exception as exc:  # incl. RecursionError: isolate to this record
                        metadata["evtx_user_data_error"] = type(exc).__name__

                # Standardize specific fields for Anomaly Engine (first occurrence of each Name)
                target_user = named.get("TargetUserName")
                workstation = named.get("WorkstationName")
                ip_address = named.get("IpAddress")

                # Parser-owned evtx_* keys win over any EventData name.
                structured_meta = {**named, **metadata}
                if target_user:
                    structured_meta["target_user_name"] = target_user
                if workstation:
                    structured_meta["workstation_name"] = workstation
                if ip_address:
                    structured_meta["source_network_ip"] = ip_address

                yield {
                    "occurrence_time": timestamp,
                    "event_id": event_id,
                    "severity": level,
                    "event_channel": channel,
                    "metadata": structured_meta
                }
