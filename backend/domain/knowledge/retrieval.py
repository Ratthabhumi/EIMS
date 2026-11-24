"""Deterministic knowledge retrieval for the Analyzer.

Trust level comes only from the canonical catalog class and the persisted
governance overlay. Free text, model output and keyword scores never influence
it, and a stale decision or an unavailable overlay can only lower trust.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.knowledge.models import KnowledgeReview

CLASSIFICATIONS = (
    "context_match",
    "diagnostic_candidate_match",
    "source_verified_match",
    "validated_diagnostic_match",
    "approved_diagnostic_match",
    "version_compatible_match",
    "no_verified_match",
)

_BY_STATUS = {
    "candidate": "diagnostic_candidate_match",
    "source_verified": "source_verified_match",
    "validated": "validated_diagnostic_match",
    "approved": "approved_diagnostic_match",
}
_VERSION = re.compile(r"(\d+)(?:\.(\d+|x))?", re.IGNORECASE)


def version_compatibility(scope: Optional[str], detected: Optional[str]) -> Optional[bool]:
    """True/False only when both sides carry a parseable version; otherwise None."""
    if not scope or not detected:
        return None
    wanted = _VERSION.findall(str(scope))
    found = _VERSION.search(str(detected))
    if not wanted or not found:
        return None
    major, minor = found.group(1), found.group(2)
    for want_major, want_minor in wanted:
        if want_major != major:
            continue
        if not want_minor or want_minor.lower() == "x" or want_minor == minor:
            return True
    return False


def classify(
    entry: Optional[Mapping[str, Any]],
    row: Any,
    *,
    detected_version: Optional[str] = None,
    overlay_available: bool = True,
) -> dict:
    """Pure classification of one catalog match against its governance row."""
    if entry is None:
        return _result("no_verified_match", None, row, overlay_available,
                       note="No catalog record matched this evidence.")
    if entry.get("knowledge_class") == "operational_context":
        return _result("context_match", entry, row, overlay_available,
                       note="Event reference material; not a diagnostic procedure.")

    stale = bool(row is not None and row.review_required)
    status = row.lifecycle_status if (row is not None and overlay_available) else "candidate"
    if stale:
        return _result("diagnostic_candidate_match", entry, row, overlay_available, stale=True,
                       note="Prior review is stale after a content change; treated as unreviewed.")
    classification = _BY_STATUS.get(status, "no_verified_match")
    note = {
        "diagnostic_candidate_match": "Candidate knowledge; not source-verified.",
        "source_verified_match": "Source verified; not yet validated.",
        "validated_diagnostic_match": "Validated; not yet approved.",
        "approved_diagnostic_match": "Approved knowledge.",
        "no_verified_match": f"Record is {status}; no verified knowledge applies.",
    }[classification]

    compatible: Optional[bool] = None
    if classification == "approved_diagnostic_match":
        compatible = version_compatibility(getattr(row, "product_version_scope", None), detected_version)
        if compatible is True:
            classification, note = "version_compatible_match", "Approved and version-compatible."
        elif compatible is False:
            classification = "no_verified_match"
            note = "Approved only for a different product version."
    return _result(classification, entry, row, overlay_available, stale=False,
                   version_compatible=compatible, note=note)


def _result(classification, entry, row, overlay_available, *, stale=False,
            version_compatible=None, note="") -> dict:
    return {
        "classification": classification,
        "catalogId": entry.get("catalog_id") if entry else None,
        "lifecycleStatus": (row.lifecycle_status if row is not None else None),
        "stale": stale,
        "versionScope": getattr(row, "product_version_scope", None) if row is not None else None,
        "versionCompatible": version_compatible,
        "overlayAvailable": overlay_available,
        "matchKind": "direct" if entry else "none",
        "matchBasis": "identity" if entry else "no_record",
        "note": note,
    }


async def retrieve(
    db: AsyncSession,
    entry: Optional[Mapping[str, Any]],
    *,
    detected_version: Optional[str] = None,
) -> dict:
    """Look up the overlay row for ``entry`` and classify.

    The read runs in a SAVEPOINT so a missing/unreachable overlay cannot abort
    the caller's transaction (the history insert follows in the same session);
    on failure the result is explicitly marked ``overlayAvailable: false``.
    """
    if entry is None or entry.get("knowledge_class") == "operational_context":
        return classify(entry, None, detected_version=detected_version)
    try:
        async with db.begin_nested():
            row = (await db.execute(
                select(KnowledgeReview).where(KnowledgeReview.catalog_id == entry["catalog_id"])
            )).scalars().first()
    except Exception:  # noqa: BLE001 - fail to lower trust, never to higher
        return classify(entry, None, detected_version=detected_version, overlay_available=False)
    return classify(entry, row, detected_version=detected_version)



async def retrieve_windows(db: AsyncSession, event_id, provider, *, detected_version: Optional[str] = None) -> dict:
    """Provider-aware Windows retrieval. Event ID alone is never presented as a direct match.

    direct      provider and Event ID agree with the record
    contextual  Event ID matches but the provider is unspecified/unverified: shown as reference, flagged
    none        no record, or the record belongs to a different provider (explicit mismatch, not applied)
    """
    from backend.domain.analyzer.services.operational_catalog import resolve_windows_entry

    found = resolve_windows_entry(event_id, provider)
    entry, basis = found["entry"], found["basis"]
    if entry is None:
        result = classify(None, None, detected_version=detected_version)
        if basis == "provider_ambiguous":
            result["note"] = (f"Event ID {event_id} is documented for more than one provider and the event does not "
                              "say which; no record was selected.")
    elif basis == "provider_mismatch":
        result = classify(None, None, detected_version=detected_version)
        result["note"] = (f"Event ID {event_id} has a reference record for provider '{entry.get('provider')}', "
                          f"but this event comes from '{provider}'. The record was not applied.")
    else:
        result = await retrieve(db, entry, detected_version=detected_version)
        if found["kind"] == "contextual":
            # Provider not confirmed: the trust class is capped at context (never an approved/validated match).
            if result.get("classification") != "no_verified_match":
                result["classification"] = "context_match"
            reason = ("the event states no provider" if basis == "provider_unspecified"
                      else "the record's provider could not be confirmed against the event's provider")
            result["note"] = f"Event ID matches, but {reason}; use as reference only. " + result["note"]
    result["matchKind"], result["matchBasis"] = found["kind"], basis
    return result
