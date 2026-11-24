"""Read-only unified Knowledge Catalog projection.

One inventory (_catalog), explicit Analyzer vs certification dimensions.
Never sum analyzer_matchable with governed_records.
"""
from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from backend.domain.analyzer.services.operational_catalog import load_catalog
from backend.domain.knowledge.catalog_adapter import CLASSES, classify
from backend.domain.knowledge.service import _catalog, canonical_hash, catalog_kind

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ELIGIBILITY_PATH = _REPO_ROOT / "docs/acceptance/certification/catalog_import_eligibility.json"
_REGISTER_PATH = _REPO_ROOT / "docs/acceptance/certification/register.json"


@lru_cache(maxsize=1)
def _matchable_ids() -> frozenset[str]:
    return frozenset(e["catalog_id"] for e in load_catalog())


@lru_cache(maxsize=1)
def _eligibility_by_catalog_id() -> dict[str, dict]:
    if not _ELIGIBILITY_PATH.is_file():
        return {}
    data = json.loads(_ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data.get("records", []):
        cid = row.get("catalog_id")
        if isinstance(cid, str) and cid:
            out[cid] = row
        # runtime keys for candidate/reference already include prefixes on record_key
        rk = row.get("record_key")
        if isinstance(rk, str) and rk and rk not in out:
            # prefer catalog_id; also index candidate:/reference: record_keys as runtime ids
            if rk.startswith(("candidate:", "reference:")):
                out[rk] = row
            elif rk.startswith("operational:"):
                out[rk.removeprefix("operational:")] = row
            elif rk.startswith("diagnostic_legacy:"):
                out[rk.removeprefix("diagnostic_legacy:")] = row
    return out


@lru_cache(maxsize=1)
def _register_by_catalog_id() -> dict[str, dict]:
    if not _REGISTER_PATH.is_file():
        return {}
    data = json.loads(_REGISTER_PATH.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for row in data.get("records", []):
        cid = row.get("catalog_id")
        rk = row.get("record_key")
        if isinstance(cid, str) and cid:
            out[cid] = row
        if isinstance(rk, str) and rk.startswith(("candidate:", "reference:")):
            out[rk] = row
        elif isinstance(rk, str) and rk.startswith("operational:"):
            out[rk.removeprefix("operational:")] = row
        elif isinstance(rk, str) and rk.startswith("diagnostic_legacy:"):
            out[rk.removeprefix("diagnostic_legacy:")] = row
    return out


def _title(entry: dict, kind: str) -> str:
    for key in ("title", "name", "symptom", "meaning", "diagnostic_code", "code", "event_id"):
        val = entry.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return entry.get("catalog_id") or "untitled"


def _parser_linkage(catalog_id: str, entry: dict, kind: str, cert_class: str) -> str:
    if catalog_id in _matchable_ids():
        return "analyzer_matchable"
    mapping = str(entry.get("parser_mapping") or "")
    if cert_class == "B" or mapping.startswith("parser_linked_"):
        return "cert_parser_linked_only"
    if kind == "reference" and mapping == "parser_mapped":
        return "parser_mapped_reference"
    return "not_linked"


def _knowledge_type(kind: str, entry: dict, cert_class: str) -> str:
    if kind == "windows" or entry.get("knowledge_class") == "operational_context":
        return "operational_context"
    if cert_class == "D" or entry.get("detection_kind") in ("state_telemetry", "cli_state"):
        return "state_telemetry"
    if kind == "reference" or cert_class in ("C", "F"):
        return "technical_reference"
    return "diagnostic_candidate"


def _refs(entry: dict) -> list[dict]:
    raw = entry.get("official_references") or entry.get("official_sources") or []
    if isinstance(entry.get("source"), dict) and entry["source"].get("url"):
        raw = list(raw) + [entry["source"]]
    out = []
    for ref in raw if isinstance(raw, list) else []:
        if not isinstance(ref, dict):
            continue
        url = ref.get("url") or ref.get("href")
        if isinstance(url, str) and url.startswith("https://"):
            out.append({
                "title": str(ref.get("title") or ref.get("name") or "source"),
                "url": url,
                "scope": str(ref.get("scope") or ref.get("version_scope") or ""),
            })
    return out


def project_record(catalog_id: str, entry: dict) -> dict[str, Any]:
    kind = catalog_kind(catalog_id)
    cert_class = classify(kind, entry)
    matchable = catalog_id in _matchable_ids()
    elig = _eligibility_by_catalog_id().get(catalog_id) or {}
    reg = _register_by_catalog_id().get(catalog_id) or {}
    return {
        "catalog_id": catalog_id,
        "record_key": reg.get("record_key") or elig.get("record_key"),
        "inventory_scope": "governed",
        "source_catalog": {
            "windows": "operational",
            "legacy": "diagnostic_legacy",
            "candidate": "candidate",
            "reference": "reference",
        }[kind],
        "knowledge_type": _knowledge_type(kind, entry, cert_class),
        "cert_class": cert_class,
        "cert_class_name": CLASSES.get(cert_class, cert_class),
        "parser_linkage": _parser_linkage(catalog_id, entry, kind, cert_class),
        "analyzer_availability": "matchable" if matchable else "not_matchable",
        "eligibility": elig.get("status"),
        "eligibility_source": "catalog_import_eligibility.json" if elig else None,
        "source_verification": (reg.get("readiness") or {}).get("source") if isinstance(reg.get("readiness"), dict) else None,
        "human_approval": (reg.get("readiness") or {}).get("approval") if isinstance(reg.get("readiness"), dict) else "NOT_APPROVED",
        "product": entry.get("product") or reg.get("product"),
        "vendor": entry.get("vendor") or reg.get("vendor"),
        "version_scope": entry.get("version_scope") or entry.get("compatibility_scope") or reg.get("version_scope"),
        "title": _title(entry, kind),
        "category": entry.get("category") or entry.get("problem_domain") or entry.get("domain"),
        "description": entry.get("description") or entry.get("meaning") or entry.get("symptom") or "",
        "severity": entry.get("severity") or "info",
        "event_id": entry.get("event_id") or entry.get("diagnostic_code") or entry.get("code") or "",
        "source_family": entry.get("source_family") or entry.get("product_family") or kind,
        "provider": entry.get("provider") or entry.get("product") or entry.get("vendor") or "",
        "code_type": entry.get("code_type") or "",
        "diagnostic_code": entry.get("diagnostic_code") or entry.get("code") or "",
        "support_level": entry.get("support_level") or entry.get("evidence_maturity") or "",
        "verification_status": entry.get("verification_status") or entry.get("review_status") or "",
        "knowledge_class": entry.get("knowledge_class") or _knowledge_type(kind, entry, cert_class),
        "lifecycle_status": entry.get("lifecycle_status") or "candidate",
        "keywords": entry.get("keywords") or entry.get("observed_signatures") or entry.get("signatures") or [],
        "official_references": _refs(entry),
        "source_references": _refs(entry),
        "content_hash": canonical_hash({k: v for k, v in entry.items() if k != "catalog_id"}),
    }


@lru_cache(maxsize=1)
def all_projected() -> tuple[dict, ...]:
    records = tuple(project_record(cid, entry) for cid, entry in sorted(_catalog().items()))
    return records


def compute_totals(records: Iterable[dict] | None = None) -> dict[str, Any]:
    rows = list(records) if records is not None else list(all_projected())
    elig = Counter(r.get("eligibility") for r in rows if r.get("eligibility"))
    return {
        "governed_records": len(rows),
        "analyzer_matchable": sum(1 for r in rows if r["analyzer_availability"] == "matchable"),
        "other_governed": sum(1 for r in rows if r["analyzer_availability"] == "not_matchable"),
        "cert_class_b": sum(1 for r in rows if r["cert_class"] == "B"),
        "cert_class_b_analyzer_matchable": sum(
            1 for r in rows if r["cert_class"] == "B" and r["analyzer_availability"] == "matchable"
        ),
        "cert_class_b_not_in_load_catalog": sum(
            1 for r in rows if r["cert_class"] == "B" and r["analyzer_availability"] == "not_matchable"
        ),
        "eligible": elig.get("ELIGIBLE", 0),
        "blocked": elig.get("BLOCKED", 0),
        "ineligible": elig.get("INELIGIBLE", 0),
        "human_approved": sum(1 for r in rows if r.get("human_approval") == "APPROVED"),
        "by_cert_class": dict(Counter(r["cert_class"] for r in rows)),
        "by_parser_linkage": dict(Counter(r["parser_linkage"] for r in rows)),
        # Product-family distribution for Analyzer-matchable subset only (sums to analyzer_matchable).
        "by_analyzer_source_family": dict(
            Counter(
                r.get("source_family") or "unknown"
                for r in rows
                if r["analyzer_availability"] == "matchable"
            )
        ),
        "note": (
            "Catalog identities (do not sum): governed_records=911 inventory; "
            "analyzer_matchable=181 parser-linked Analyzer surface (exact subset of 911 by catalog_id); "
            "other_governed=730 = 911-181; cert_class_b=39 classification metric (28 matchable + 11 not in load_catalog); "
            "175 is a historical Gate-H snapshot of the Analyzer surface, not an extra catalog. "
            "eligible is not human-approved."
        ),
        "count_semantics": {
            "governed_records": "Full governed inventory (_catalog / register)",
            "analyzer_matchable": "Parser-linked Analyzer catalog (load_catalog); distinct surface, proven subset of governed",
            "other_governed": "Governed records outside Analyzer loader (911-181)",
            "cert_class_b": "Certification class B metric; not a catalog total",
            "eligible": "Import eligibility for human-review registration; not human-approved",
            "human_approved": "Human certification decisions only (0 while NOT RUN)",
            "historical_175": "2026-11-20 Gate H snapshot of Analyzer surface before +6 ASA; not a current source",
        },
    }


def identity_evidence() -> dict[str, Any]:
    """Machine-verifiable Phase-1 claims for delivery evidence."""
    linked = _matchable_ids()
    gov = set(_catalog().keys())
    rows = list(all_projected())
    hashes = [r["content_hash"] for r in rows]
    class_b = [r for r in rows if r["cert_class"] == "B"]
    b_out = [r["catalog_id"] for r in class_b if r["analyzer_availability"] == "not_matchable"]
    return {
        "governed_count": len(gov),
        "unique_catalog_id_count": len(gov),
        "duplicate_catalog_ids": [],
        "analyzer_matchable_count": len(linked),
        "intersection_count": len(linked & gov),
        "only_in_analyzer_loader": sorted(linked - gov),
        "other_governed_count": len(gov - linked),
        "strict_subset": linked <= gov,
        "difference_equals_other": len(gov - linked) == len(gov) - len(linked),
        "unique_content_hashes": len(set(hashes)),
        "content_hash_collisions": len(hashes) - len(set(hashes)),
        "cert_class_b_count": len(class_b),
        "cert_class_b_in_load_catalog": sum(1 for r in class_b if r["analyzer_availability"] == "matchable"),
        "cert_class_b_not_in_load_catalog": len(b_out),
        "cert_class_b_not_in_load_catalog_ids": sorted(b_out),
        "b_membership_identity": (
            sum(1 for r in class_b if r["analyzer_availability"] == "matchable") + len(b_out) == len(class_b)
        ),
        "totals": compute_totals(rows),
    }


def list_catalog(
    *,
    q: str | None = None,
    parser_linkage: str | None = None,
    analyzer_availability: str | None = None,
    eligibility: str | None = None,
    cert_class: str | None = None,
    product: str | None = None,
    offset: int = 0,
    limit: int = 50,
    sort: str = "catalog_id",
) -> dict[str, Any]:
    rows = list(all_projected())
    totals = compute_totals(rows)

    def ok(r: dict) -> bool:
        if parser_linkage and r["parser_linkage"] != parser_linkage:
            return False
        if analyzer_availability and r["analyzer_availability"] != analyzer_availability:
            return False
        if eligibility and r.get("eligibility") != eligibility:
            return False
        if cert_class and r["cert_class"] != cert_class:
            return False
        if product and str(r.get("product") or "").casefold() != product.casefold():
            return False
        if q:
            blob = " ".join(
                str(r.get(k) or "")
                for k in ("catalog_id", "title", "product", "vendor", "category", "cert_class", "knowledge_type")
            ).casefold()
            if q.casefold() not in blob:
                return False
        return True

    filtered = [r for r in rows if ok(r)]
    reverse = sort.startswith("-")
    key = sort.lstrip("-") or "catalog_id"
    filtered.sort(key=lambda r: str(r.get(key) or ""), reverse=reverse)
    page = filtered[offset : offset + limit]
    return {
        "surface": "unified_governed_catalog",
        "schema_version": 1,
        "totals": totals,
        "filtered_count": len(filtered),
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "records": page,
    }


def clear_caches() -> None:
    _matchable_ids.cache_clear()
    _eligibility_by_catalog_id.cache_clear()
    _register_by_catalog_id.cache_clear()
    all_projected.cache_clear()
