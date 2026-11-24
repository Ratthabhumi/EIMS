import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.models.knowledge import KnowledgeEntry

# Families whose diagnostic code is only meaningful together with a provider (Windows Event IDs are reused by
# unrelated providers). Other families use vendor-unique codes: the family itself is the scope.
PROVIDER_BEARING_FAMILIES = frozenset({"windows_event"})
_UNSPECIFIED = {"", "unknown", "none", "n/a", "-", "null"}


def norm_provider(value) -> str:
    text = re.sub(r"\s+", " ", str(value if value is not None else "")).strip().casefold()
    return "" if text in _UNSPECIFIED else text


def derive_provider_scope(source_family: str, provider, declared: str | None = None) -> tuple[str | None, str]:
    """(provider, provider_scope) for a new proposal. The provider comes only from the analysed record, never from
    an Event ID; a missing provider on a provider-bearing family is recorded as 'unknown', not guessed."""
    family = str(source_family or "").strip().lower()
    clean = str(provider).strip()[:160] if norm_provider(provider) else None
    if family not in PROVIDER_BEARING_FAMILIES:
        return clean, "vendor_product"
    if declared == "generic":
        return None, "generic"
    if clean:
        return clean, "provider_specific"
    return None, "unknown"


def classify_candidate(entry: KnowledgeEntry, family: str, provider: str) -> tuple[str, str] | None:
    """Return (match_kind, reason) when ``entry`` may be shown for this lookup, or None when it must be withheld.

    match_kind: ``provider_exact`` | ``vendor_identity`` | ``generic_context``.
    """
    scope = entry.provider_scope or "unknown"
    if family not in PROVIDER_BEARING_FAMILIES:
        if scope in {"vendor_product", "unknown", "provider_specific", "generic"}:
            return "vendor_identity", "Vendor code is unique within the source family; no provider is involved."
        return None
    wanted = norm_provider(provider)
    if scope == "provider_specific":
        if wanted and norm_provider(entry.provider) == wanted:
            return "provider_exact", f"Exact provider '{entry.provider}' and identity."
        return None  # other provider, or caller provider unknown: never exact
    if scope == "generic":
        return "generic_context", "Explicitly provider-independent guidance; contextual only."
    return None  # legacy 'unknown' / 'unverified' / 'vendor_product' on a provider-bearing family


async def search_approved_knowledge(
    db: AsyncSession,
    source_family: str,
    diagnostic_identity: str,
    provider: str | None = None,
) -> dict | None:
    """Return one human-approved case for the exact identity, provider-isolated for provider-bearing families.

    Provider-specific entries are returned only for the same provider. Provider-unknown legacy entries never match a
    provider-bearing family; generic entries come back as contextual. Never crosses source families or codes.
    """
    family = str(source_family or "").strip().lower()
    identity = str(diagnostic_identity or "").strip()
    if not family or family == "unknown_text" or not identity or identity == "Unknown":
        return None

    rows = (
        await db.execute(
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.status == "approved",
                KnowledgeEntry.lifecycle_state == "active",
                KnowledgeEntry.source_family == family,
                KnowledgeEntry.diagnostic_identity == identity,
            )
            .order_by(KnowledgeEntry.reviewed_at.desc(), KnowledgeEntry.id.desc())
        )
    ).scalars().all()
    ranked = {"provider_exact": 0, "vendor_identity": 0, "generic_context": 1}
    chosen = None
    for row in rows:
        verdict = classify_candidate(row, family, provider or "")
        if verdict is None:
            continue
        if chosen is None or ranked[verdict[0]] < ranked[chosen[1][0]]:
            chosen = (row, verdict)
    if chosen is None:
        return None
    entry, (kind, reason) = chosen

    steps = [*(f"Prerequisite: {item}" for item in (entry.prerequisites or [])), *(entry.solution_steps or [])]
    steps.extend(f"Validation: {item}" for item in (entry.validation_steps or []))
    steps.extend(f"Rollback: {item}" for item in (entry.rollback_steps or []))
    if entry.prevention:
        steps.append(f"Prevention: {entry.prevention}")
    evidence = [
        (
            f"Approved knowledge entry #{entry.id}; reviewed by {entry.reviewed_by} "
            f"at {entry.reviewed_at.isoformat() if entry.reviewed_at else 'unknown time'}."
        ),
        f"Source incident SHA-256: {entry.source_history_hash}",
        f"Approved-knowledge match: {kind} - {reason}",
        *(str(note) for note in (entry.evidence_notes or [])),
        *(f"Reference: {url}" for url in (entry.references or [])),
    ]
    if kind == "generic_context":
        limitations = [
            "Contextual match only: this approved entry is explicitly provider-independent and is not a "
            "provider-specific diagnosis for this event."
        ]
    else:
        limitations = [
            "Verified for a recorded incident with this exact diagnostic identity; validate environment-specific prerequisites before execution."
        ]
    if entry.impact:
        limitations.append(f"Recorded impact: {entry.impact}")
    applicability = ", ".join(value for value in (entry.product_name, entry.product_version, entry.environment) if value)
    if applicability:
        limitations.append(f"Recorded applicability: {applicability}; confirm it matches the current environment.")
    limitations.append(f"Recorded remediation risk level: {entry.risk_level}.")
    if entry.resolution_status == "partially_resolved":
        limitations.append("The recorded outcome was partially resolved, not a complete fix.")

    confident = entry.resolution_status == "resolved" and kind != "generic_context"
    return {
        "overview": entry.root_cause,
        "causes": [entry.root_cause],
        "steps": steps,
        "evidence": evidence,
        "confidence": "high" if confident else "medium",
        "limitations": limitations,
    }
