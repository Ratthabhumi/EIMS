"""Versioned static diagnostic knowledge; never runtime analysis records."""
import copy
import json
import re
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("operational_event_catalog.json")
VENDOR_CATALOG_PATH = Path(__file__).with_name("diagnostic_knowledge_catalog.json")


GUIDANCE_LISTS = ("expected_findings", "safe_remediation", "verification_criteria")
GUIDANCE_TEXT = ("risk", "rollback", "evidence_basis")
GUIDANCE_LOCALIZED = ("th", "en")


def _validate_references(refs) -> None:
    if not isinstance(refs, list):
        raise ValueError("Invalid official references")
    for ref in refs:
        if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k]
                for k in ("title", "url", "scope")) or not ref["url"].startswith("https://"):
            raise ValueError("Invalid official reference")


def _validate_guidance(guidance) -> None:
    """Optional structured guidance; unknown keys and wrong types fail closed.

    `evidence_basis` is mandatory whenever guidance exists, so every statement stays traceable to its source.
    """
    if guidance is None:
        return
    allowed = set(GUIDANCE_LISTS) | set(GUIDANCE_TEXT) | {"localized_summary"}
    if not isinstance(guidance, dict) or set(guidance) - allowed:
        raise ValueError("Invalid diagnostic_guidance")
    for key in GUIDANCE_LISTS:
        value = guidance.get(key, [])
        if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
            raise ValueError(f"Invalid diagnostic_guidance.{key}")
    for key in GUIDANCE_TEXT:
        if key in guidance and (not isinstance(guidance[key], str) or not guidance[key].strip()):
            raise ValueError(f"Invalid diagnostic_guidance.{key}")
    summary = guidance.get("localized_summary")
    if summary is not None:
        # Same shape the Analyzer renders (overview/causes/steps) per language.
        if not isinstance(summary, dict) or set(summary) - set(GUIDANCE_LOCALIZED):
            raise ValueError("Invalid diagnostic_guidance.localized_summary")
        for body in summary.values():
            if (not isinstance(body, dict) or set(body) - {"overview", "causes", "steps"}
                    or not isinstance(body.get("overview"), str)
                    or any(not isinstance(body.get(k, []), list) or any(not isinstance(v, str) for v in body.get(k, []))
                           for k in ("causes", "steps"))):
                raise ValueError("Invalid diagnostic_guidance.localized_summary")
    if not guidance.get("evidence_basis"):
        raise ValueError("diagnostic_guidance requires evidence_basis")


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
        _validate_references(raw.get("official_references", []))
        _validate_guidance(raw.get("diagnostic_guidance"))
        names = raw.get("provider_names", [])
        if not isinstance(names, list) or any(not isinstance(n, str) or not n.strip() for n in names):
            raise ValueError("Invalid provider_names")
        result.append(dict(raw, source_family="windows_event", vendor="Microsoft",
                           product="Microsoft Windows", code_type="official_event_id",
                           diagnostic_code=raw.get("diagnostic_code", raw["event_id"]),
                           support_level="legacy_reference",
                           verification_status="preserved_legacy",
                           official_references=list(raw.get("official_references", [])),
                           knowledge_class="operational_context",
                           lifecycle_status="operational_context"))
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
        _validate_references(raw["official_references"])
        _validate_guidance(raw.get("diagnostic_guidance"))
        if raw["source_family"] in ("windows_event", "json", "unknown_text"):
            raise ValueError("Vendor catalog cannot redefine legacy or generic knowledge")
        result.append(dict(raw, event_id=raw["diagnostic_code"], provider=raw["product"],
                           keywords=raw.get("observed_signatures", []), related_events=raw.get("related_codes", []),
                           operator_context=raw.get("limitations", ""),
                           knowledge_class="diagnostic_candidate",
                           lifecycle_status="candidate"))
    for entry in result:
        identity = (entry["source_family"], entry["code_type"], entry["diagnostic_code"])
        if identity in seen:
            raise ValueError(f"Duplicate catalog identity: {identity}")
        seen.add(identity)
        entry["catalog_id"] = ":".join(identity)
    return result


OPERATIONAL_CATALOG = load_catalog()
# Legacy primary record per Event ID (stable identity ``windows_event:official_event_id:<id>``).
CATALOG_BY_ID = {e["event_id"]: e for e in OPERATIONAL_CATALOG
                 if e["source_family"] == "windows_event" and e["diagnostic_code"] == e["event_id"]}
# Every Windows record per Event ID, including provider-qualified ones (diagnostic_code ``<id>:<provider>``).
WINDOWS_BY_EVENT_ID: dict[str, list[dict]] = {}
for _e in OPERATIONAL_CATALOG:
    if _e["source_family"] == "windows_event":
        WINDOWS_BY_EVENT_ID.setdefault(_e["event_id"], []).append(_e)
CATALOG_BY_IDENTITY = {(e["source_family"], e["code_type"], e["diagnostic_code"]): e for e in OPERATIONAL_CATALOG}


_PROVIDER_PREFIX = "microsoft-windows-"
_UNSPECIFIED = {"", "unknown", "none", "n/a", "-"}


def normalize_provider(value) -> str:
    """Case/space/prefix-insensitive provider key; '' when the provider is not stated."""
    text = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    if text in _UNSPECIFIED:
        return ""
    return text[len(_PROVIDER_PREFIX):] if text.startswith(_PROVIDER_PREFIX) else text


def _label_keys(label: str) -> set[str]:
    keys = {normalize_provider(label)}
    keys.update(normalize_provider(part) for part in re.split(r"[/()]", label or "") if part.strip())
    return {k for k in keys if k}


def resolve_windows_entry(event_id, provider) -> dict:
    """Provider-aware lookup of a Windows reference record. Never guesses.

    basis:
      provider_and_id       direct: the event's provider is a known provider of exactly one record
      provider_unspecified  the event states no provider and one record exists: shown as contextual reference
      provider_ambiguous    several providers share this Event ID and the event does not decide between them
      provider_unverified   provider stated, record has no verified provider names and the label does not match
      provider_mismatch     every record for this ID carries verified provider names and none is the event's provider
      no_record             no record for this Event ID
    The Event ID alone is never a direct match; stable catalog IDs are unchanged.
    """
    candidates = WINDOWS_BY_EVENT_ID.get(str(event_id), []) if event_id is not None else []
    if not candidates:
        return {"entry": None, "basis": "no_record", "kind": "none"}
    given = normalize_provider(provider)

    def keys(entry):
        verified = {normalize_provider(n) for n in entry.get("provider_names", [])}
        return verified, verified | _label_keys(entry.get("provider", ""))

    if not given:
        if len(candidates) > 1:
            return {"entry": None, "basis": "provider_ambiguous", "kind": "none",
                    "candidates": [c["catalog_id"] for c in candidates]}
        return {"entry": candidates[0], "basis": "provider_unspecified", "kind": "contextual"}
    direct = [c for c in candidates if given in keys(c)[1]]
    if len(direct) == 1:
        return {"entry": direct[0], "basis": "provider_and_id", "kind": "direct"}
    if len(direct) > 1:
        return {"entry": None, "basis": "provider_ambiguous", "kind": "none",
                "candidates": [c["catalog_id"] for c in direct]}
    unverified = [c for c in candidates if not keys(c)[0]]
    if unverified:
        return {"entry": unverified[0], "basis": "provider_unverified", "kind": "contextual"}
    return {"entry": candidates[0], "basis": "provider_mismatch", "kind": "none"}


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


def knowledge_summary() -> dict:
    """Class-based counters. A candidate is NOT validated diagnostic knowledge.

    Counts are derived from the loaded catalog, never from the UI. ``validated``
    and ``approved`` are zero until a record actually passes the quality gate,
    which does not exist yet.
    """
    from collections import Counter

    context = [e for e in OPERATIONAL_CATALOG if e.get("knowledge_class") == "operational_context"]
    candidates = [e for e in OPERATIONAL_CATALOG if e.get("knowledge_class") == "diagnostic_candidate"]

    def has(entry: dict, key: str) -> bool:
        value = entry.get(key)
        return bool(value)

    return {
        "source": "operational_event_catalog.json + diagnostic_knowledge_catalog.json",
        "total_records": len(OPERATIONAL_CATALOG),
        "counts": {
            "operational_context": len(context),
            "diagnostic_candidates": len(candidates),
            "source_verified": 0,
            "validated": 0,
            "approved": 0,
            "deprecated": 0,
        },
        "products": dict(Counter(e.get("product") or e.get("vendor") for e in OPERATIONAL_CATALOG)),
        "candidate_field_coverage": {
            "investigation_steps": sum(1 for e in candidates if has(e, "investigation_steps")),
            "official_references": sum(1 for e in candidates if has(e, "official_references")),
            "limitations": sum(1 for e in candidates if has(e, "limitations")),
            "remediation_guidance": sum(1 for e in candidates if has(e, "remediation_guidance")),
            "verification_criteria": sum(1 for e in candidates if has(e, "verification_criteria")),
            "source_verified_at": sum(1 for e in candidates if has(e, "verified_at")),
        },
        "note": (
            "operational_context is event reference material, not a diagnostic "
            "procedure. diagnostic_candidate has diagnostic intent but has not "
            "passed the quality gate."
        ),
    }
