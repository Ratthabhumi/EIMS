import io
from collections.abc import Generator
from typing import Any
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

NS = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}

LEVEL_MAP = {
    "1": "Critical",
    "2": "Error",
    "3": "Warning",
    "4": "Information",
    "5": "Verbose",
}


def _text(elem: Element | None) -> str:
    return (elem.text or "").strip() if elem is not None else ""


def parse_evtx_records(content: bytes) -> Generator[dict[str, Any], None, None]:
    """
    Parses a raw Windows .evtx binary file and yields structured dictionary
    records matching the EIMS WindowsEventLog payload schema.
    """
    try:
        from Evtx.Evtx import Evtx
    except ImportError:
        raise RuntimeError("python-evtx is not installed.")

    with Evtx(io.BytesIO(content)) as log:
        for record in log.records():
            xml_str = record.xml()
            try:
                root = ET.fromstring(xml_str)
            except ET.ParseError:
                continue

            system = root.find("e:System", NS)
            if system is None:
                continue

            event_id_str = _text(system.find("e:EventID", NS))
            if not event_id_str.isdigit():
                continue
                
            event_id = int(event_id_str)
            level_raw = _text(system.find("e:Level", NS))
            level = LEVEL_MAP.get(level_raw, "Information")
            channel = _text(system.find("e:Channel", NS))

            time_elem = system.find("e:TimeCreated", NS)
            timestamp = time_elem.get("SystemTime", "") if time_elem is not None else ""

            # Extract EventData as metadata
            metadata = {}
            event_data = root.find("e:EventData", NS)
            if event_data is not None:
                for data in event_data.findall("e:Data", NS):
                    name = data.get("Name", "")
                    value = _text(data)
                    if name and value:
                        metadata[name] = value

            # Standardize specific fields for Anomaly Engine
            target_user = metadata.get("TargetUserName")
            workstation = metadata.get("WorkstationName")
            ip_address = metadata.get("IpAddress")
            
            structured_meta = {k: v for k, v in metadata.items()}
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
