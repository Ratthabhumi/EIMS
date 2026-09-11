"""Operational Event Catalog loader.

STATIC catalog (no DB): ~141 common Windows/infrastructure/security events.
Distinct provenance from analysis_history — these are KNOWLEDGE entries,
never counted as analyzed logs.
"""
import json
import os

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "operational_event_catalog.json")

with open(CATALOG_PATH, encoding="utf-8") as _f:
    OPERATIONAL_CATALOG = json.load(_f)

# Fast exact-id lookup (first match wins; ids are unique in the catalog)
CATALOG_BY_ID = {entry["event_id"]: entry for entry in OPERATIONAL_CATALOG}


def get_catalog() -> list[dict]:
    """Return the full operational event catalog (read-only)."""
    return list(OPERATIONAL_CATALOG)


def get_catalog_entry(event_id: str) -> dict | None:
    """Return a single catalog entry by exact event id."""
    return CATALOG_BY_ID.get(event_id)