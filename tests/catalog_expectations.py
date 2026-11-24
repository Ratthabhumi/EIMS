"""Catalog expectations derived from the catalog source files, not pinned to a record count.

Brittle `== 181` style assertions break on every legitimate catalog addition. Business invariants
that must hold regardless of growth: the 163-ID baseline is preserved, the Windows operational
context set is the legacy 153, every vendor entry is a diagnostic_candidate, and the loaded catalog
is exactly the two source files, with no duplicates.
"""
import json
from collections import Counter
from pathlib import Path

SERVICES = Path(__file__).resolve().parents[1] / "backend/domain/analyzer/services"
WINDOWS = json.loads((SERVICES / "operational_event_catalog.json").read_text(encoding="utf-8"))
VENDOR = json.loads((SERVICES / "diagnostic_knowledge_catalog.json").read_text(encoding="utf-8"))["entries"]
BASELINE_IDS = set(json.loads((Path(__file__).with_name("data") / "knowledge_baseline_ids_20261119.json")
                              .read_text(encoding="utf-8"))["ids"])
LEGACY_WINDOWS_COUNT = 153  # intentionally protected: legacy operational_context baseline

WINDOWS_COUNT = len(WINDOWS)
VENDOR_COUNT = len(VENDOR)
TOTAL = WINDOWS_COUNT + VENDOR_COUNT
VENDOR_BY_FAMILY = dict(Counter(e["source_family"] for e in VENDOR))
