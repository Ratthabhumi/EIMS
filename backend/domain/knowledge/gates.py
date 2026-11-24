"""Destination-state quality gates for knowledge lifecycle transitions.

Pure and database-free: ``evaluate_gate`` returns ``(problems, permission)``
lists and never mutates anything, so the service can validate *before* it
changes state. Content fields that already live in the canonical catalog
(limitations, investigation steps) are accepted from the entry; everything that
is a *review decision* must be supplied in the structured ``review`` payload and
is persisted on the append-only event.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

SOURCE_FIELDS = (
    "source_title", "source_url", "supporting_section", "claim_evidence",
    "verified_at", "verifier", "vendor_product_scope",
)
# Decisions that only an authenticated human may take. AI assistants and automation may collect evidence and may reopen or
# reject (the safe direction) but can never verify, validate, approve, deprecate or supersede. Fail closed: an unknown or
# missing actor kind is not a human.
HUMAN_ONLY_TARGETS = frozenset({"source_verified", "validated", "approved", "deprecated", "superseded"})
VALIDATION_FIELDS = (
    "product_version_scope", "applicability", "validation_basis", "verification_criteria",
)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return any(_present(v) for v in (value.values() if isinstance(value, dict) else value))
    return True


def _missing(review: Mapping[str, Any], fields: Iterable[str]) -> list[str]:
    return [f"{f} is required" for f in fields if not _present(review.get(f))]


def _human_event(event: dict) -> bool:
    """Legacy events carry no actor kind: they are not accepted as human evidence."""
    return (event.get("evidence") or {}).get("actor_kind") == "human"


def _last(events: list[dict], status: str) -> dict | None:
    for event in reversed(events):
        if event.get("to_status") == status:
            return event
    return None


def evaluate_gate(
    entry: Mapping[str, Any],
    current: str,
    target: str,
    *,
    actor: str,
    rationale: str,
    review: Mapping[str, Any],
    events: list[dict],
    content_hash: str,
    review_required: bool,
    contributor: str | None,
    known_ids: set[str],
    actor_kind: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (field/content problems, permission problems) for ``current -> target``."""
    problems: list[str] = []
    permission: list[str] = []
    review = review or {}

    if not _present(actor):
        permission.append("an authenticated actor is required")
    if not _present(rationale):
        problems.append("a rationale is required")
    if target in HUMAN_ONLY_TARGETS and actor_kind != "human":
        permission.append(f"{target} is a human decision: actor_kind must be 'human' (got {actor_kind!r})")

    if target == "candidate":
        # Reopened for review: explicitly unverified again; id/class/hash are
        # derived from the canonical entry, so only actor + rationale are needed.
        return problems, permission

    if target == "source_verified":
        problems += _missing(review, SOURCE_FIELDS)
        url = str(review.get("source_url") or "").strip()
        if url:
            parts = urlsplit(url)
            if parts.scheme != "https" or not parts.netloc or " " in url:
                problems.append("source_url must be an https URL")
        stamp = review.get("verified_at")
        if _present(stamp):
            try:
                datetime.fromisoformat(str(stamp))
            except ValueError:
                problems.append("verified_at must be an ISO-8601 timestamp")
        if _present(review.get("verifier")) and _present(actor) \
                and str(review["verifier"]).strip() != actor.strip():
            permission.append("verifier must be the authenticated actor")
        if not (_present(review.get("limitations")) or _present(entry.get("limitations"))):
            problems.append("limitations is required")

    elif target == "validated":
        problems += _missing(review, VALIDATION_FIELDS)
        if not (_present(review.get("investigation_steps")) or _present(entry.get("investigation_steps")) or _present(entry.get("diagnostic_steps"))):
            problems.append("investigation_steps is required")
        if not (_present(review.get("limitations")) or _present(entry.get("limitations"))):
            problems.append("limitations is required")
        source = _last(events, "source_verified")
        if source is None:
            problems.append("a prior source_verified decision with provenance is required")
        elif source.get("source_hash") != content_hash:
            problems.append("source_verified was recorded for a different content revision")
        elif not _human_event(source):
            problems.append("the prior source_verified decision was not recorded by a human actor")

    elif target == "approved":
        validated = _last(events, "validated")
        source = _last(events, "source_verified")
        if validated is None or source is None:
            problems.append("a prior validated decision (with source provenance) is required")
        else:
            if validated.get("source_hash") != content_hash or source.get("source_hash") != content_hash:
                problems.append("validation was recorded for a different content revision")
            if not (_human_event(validated) and _human_event(source)):
                problems.append("prior source_verified/validated decisions must have been recorded by human actors")
            prior = {str(validated.get("actor", "")).strip(), str(source.get("actor", "")).strip()}
            if actor and actor.strip() in prior:
                permission.append("approver must be independent of the verifier and validator")
        if review_required:
            problems.append("record is stale and requires renewed review")
        if contributor and actor and contributor.strip() == actor.strip():
            permission.append("self-approval is not permitted")

    elif target in {"rejected", "deprecated", "superseded"}:
        if target == "superseded":
            replacement = str(review.get("replacement_catalog_id") or "").strip()
            if not replacement:
                problems.append("replacement_catalog_id is required")
            elif replacement == entry.get("catalog_id") or replacement not in known_ids:
                problems.append("replacement_catalog_id must reference a different known record")
        if not _present(content_hash):
            problems.append("source provenance hash is required")

    return problems, permission
