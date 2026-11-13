"""Versioned static diagnostic knowledge; never runtime analysis records."""
import copy
import json
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("operational_event_catalog.json")
VENDOR_CATALOG_PATH = Path(__file__).with_name("diagnostic_knowledge_catalog.json")


def load_catalog(windows_path=CATALOG_PATH, vendor_path=VENDOR_CATALOG_PATH):
    """Fail explicitly on malformed/duplicate knowledge rather than misdiagnose."""
    windows = json.loads(Path(windows_path).read_text(encoding="utf-8"))
    vendor = json.loads(Path(vendor_path).read_text(encoding="utf-8"))
    if not isinstance(windows, list) or not isinstance(vendor, dict) or vendor.get("schema_version") != 1:
        raise ValueError("Unsupported catalog structure/version")
    entries = vendor.get("entries")
    if not isinstance(entries, list):
        raise ValueError("Catalog entries must be a list")
    result, seen = [], set()
    for raw in windows:
        if not isinstance(raw, dict) or not isinstance(raw.get("event_id"), str):
            raise ValueError("Invalid legacy Windows entry")
        result.append(dict(raw, source_family="windows_event", vendor="Microsoft",
                           product="Microsoft Windows", code_type="official_event_id",
                           diagnostic_code=raw["event_id"], support_level="legacy_reference",
                           verification_status="preserved_legacy", official_references=[]))
    for raw in entries:
        if not isinstance(raw, dict) or any(not isinstance(raw.get(k), str) or not raw[k].strip()
                for k in ("source_family", "vendor", "product", "code_type", "diagnostic_code",
                          "title", "category", "severity", "description", "support_level", "verification_status")):
            raise ValueError("Invalid vendor catalog entry")
        for key in ("observed_signatures", "relevant_log_fields", "investigation_steps", "official_references"):
            if not isinstance(raw.get(key), list):
                raise ValueError(f"Invalid catalog field: {key}")
            if key != "official_references" and any(not isinstance(v, str) for v in raw[key]):
                raise ValueError(f"Invalid catalog values: {key}")
        for ref in raw["official_references"]:
            if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k]
                    for k in ("title", "url", "scope")) or not ref["url"].startswith("https://"):
                raise ValueError("Invalid official reference")
        if raw["source_family"] in ("windows_event", "json", "unknown_text"):
            raise ValueError("Vendor catalog cannot redefine legacy or generic knowledge")
        result.append(dict(raw, event_id=raw["diagnostic_code"], provider=raw["product"],
                           keywords=raw.get("observed_signatures", []), related_events=raw.get("related_codes", []),
                           operator_context=raw.get("limitations", "")))
    for entry in result:
        identity = (entry["source_family"], entry["code_type"], entry["diagnostic_code"])
        if identity in seen:
            raise ValueError(f"Duplicate catalog identity: {identity}")
        seen.add(identity)
        entry["catalog_id"] = ":".join(identity)
    return result


OPERATIONAL_CATALOG = load_catalog()
CATALOG_BY_ID = {e["event_id"]: e for e in OPERATIONAL_CATALOG if e["source_family"] == "windows_event"}
CATALOG_BY_IDENTITY = {(e["source_family"], e["code_type"], e["diagnostic_code"]): e for e in OPERATIONAL_CATALOG}


def get_catalog(source_family: str | None = None) -> list[dict]:
    return copy.deepcopy([e for e in OPERATIONAL_CATALOG if source_family is None or e["source_family"] == source_family])


def get_catalog_entry(event_id: str, source_family: str = "windows_event", code_type: str | None = None) -> dict | None:
    """Legacy calls remain Windows-only. Ambiguous qualified calls fail closed."""
    matches = [e for (family, kind, code), e in CATALOG_BY_IDENTITY.items()
               if family == source_family and code == str(event_id) and (code_type is None or kind == code_type)]
    return copy.deepcopy(matches[0]) if len(matches) == 1 else None


def entry_for_metadata(meta) -> dict | None:
    """Resolve only identities established by a dedicated parser."""
    family = meta.sourceFamily
    attrs = meta.attributes or {}
    if family in ("json", "unknown_text", ""):
        return None
    if family == "cisco_asa" and attrs.get("deviceType") != "ASA":
        return None
    return get_catalog_entry(meta.diagnosticCode or meta.eventId, family, attrs.get("codeType"))
