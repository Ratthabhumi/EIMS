"""Vendor Reference Knowledge inventory (definition tables, not diagnostics).

Deliberately separate from OPERATIONAL_CATALOG: records here have no EIMS parser
or signature mapping, so the Analyzer cannot match them and they must never be
counted or shown as diagnostic candidates, validated or approved knowledge.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REFERENCE_CATALOG_PATH = Path(__file__).with_name("vendor_reference_catalog.json")
ALLOWED_MATURITY = {"candidate", "source_referenced"}  # nothing here may claim more
ALLOWED_PARSER_MAPPING = {"parser_mapped", "missing_parser", "reference_only", "existing_parser_missing_signature",
                          "candidate_for_future_integration"}
_REQUIRED = ("reference_id", "vendor", "product", "product_family", "version_scope", "code_type", "code",
             "name", "category", "domain", "description", "knowledge_class", "evidence_maturity",
             "lifecycle_status", "parser_mapping", "limitations", "source")


def load_reference_catalog(path=REFERENCE_CATALOG_PATH) -> list[dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or not isinstance(doc.get("records"), list):
        raise ValueError("Unsupported reference catalog structure/version")
    seen, records = set(), []
    for raw in doc["records"]:
        if not isinstance(raw, dict) or any(not isinstance(raw.get(k), str) or not raw[k].strip()
                                            for k in _REQUIRED if k != "source"):
            raise ValueError("Invalid reference record")
        source = raw.get("source")
        if (not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://")
                or not source.get("title") or not source.get("retrieved") or not source.get("method")):
            raise ValueError(f"Reference record needs a complete https source: {raw['reference_id']}")
        if raw["knowledge_class"] != "reference_knowledge" or raw["lifecycle_status"] != "candidate":
            raise ValueError("Reference records are reference_knowledge candidates only")
        if raw["evidence_maturity"] not in ALLOWED_MATURITY:
            raise ValueError(f"Reference record cannot claim maturity {raw['evidence_maturity']}")
        if raw["parser_mapping"] not in ALLOWED_PARSER_MAPPING:
            raise ValueError("Invalid parser_mapping")
        if raw["parser_mapping"] == "parser_mapped" and not str(raw.get("parser_mapping_note", "")).strip():
            raise ValueError("parser_mapped requires parser_mapping_note")
        if raw.get("remediation") is not None:
            raise ValueError("Reference records carry no remediation")
        if raw["reference_id"] in seen:
            raise ValueError(f"Duplicate reference id {raw['reference_id']}")
        seen.add(raw["reference_id"])
        records.append(raw)
    return records


REFERENCE_CATALOG = load_reference_catalog()
REFERENCE_BY_ID = {r["reference_id"]: r for r in REFERENCE_CATALOG}


def reference_for_metadata(meta) -> dict | None:
    """Definition-only reference for an identity that a parser established explicitly; never guessed.

    * systemd process exit status printed by systemd itself (``codeType=process_exit_status`` on ``linux_syslog``);
      the printed name must agree with the documented name (systemd prints ``EXEC`` where the manual lists ``EXIT_EXEC``).
    * PostgreSQL SQLSTATE from a ``jsonlog`` entry (``codeType=sqlstate``, ``logFormat=postgresql_jsonlog``).
    Successful-completion states (class 00 / exit status 0) are not returned: they are not failures.
    """
    attrs = getattr(meta, "attributes", None) or {}
    family, code_type = getattr(meta, "sourceFamily", ""), attrs.get("codeType")
    if family == "linux_syslog" and code_type == "process_exit_status":
        record = REFERENCE_BY_ID.get(f"systemd:exit_status:{attrs.get('exitStatus')}")
        printed = str(attrs.get("exitName") or "")
        if record and (not printed or record["name"] in (printed, f"EXIT_{printed}")):
            return record
        return None
    if family == "json" and code_type == "sqlstate" and attrs.get("logFormat") == "postgresql_jsonlog":
        code = str(attrs.get("sqlState") or "")
        return None if code.startswith("00") else REFERENCE_BY_ID.get(f"postgresql:sqlstate:{code}")
    return None


def reference_inventory_summary(records=None) -> dict:
    records = REFERENCE_CATALOG if records is None else records

    def by(key):
        return dict(sorted(Counter(r[key] for r in records).items()))

    return {
        "total_records": len(records),
        "knowledge_class": by("knowledge_class"),
        "by_vendor": by("vendor"), "by_product": by("product"),
        "by_version_scope": by("version_scope"), "by_domain": by("domain"),
        "by_code_type": by("code_type"), "by_evidence_maturity": by("evidence_maturity"),
        "by_parser_mapping": by("parser_mapping"),
        "unique_sources": len({r["source"]["url"] for r in records}),
        "source_verified": 0, "validated": 0, "approved": 0,
    }
