from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.models.knowledge import KnowledgeEntry


async def search_approved_knowledge(
    db: AsyncSession,
    source_family: str,
    diagnostic_identity: str,
) -> dict | None:
    """Return one human-approved exact-identity case; never cross source families/codes."""
    family = str(source_family or "").strip().lower()
    identity = str(diagnostic_identity or "").strip()
    if not family or family == "unknown_text" or not identity or identity == "Unknown":
        return None

    entry = (
        await db.execute(
            select(KnowledgeEntry)
            .where(
                KnowledgeEntry.status == "approved",
                KnowledgeEntry.lifecycle_state == "active",
                KnowledgeEntry.source_family == family,
                KnowledgeEntry.diagnostic_identity == identity,
            )
            .order_by(KnowledgeEntry.reviewed_at.desc(), KnowledgeEntry.id.desc())
            .limit(1)
        )
    ).scalars().first()
    if entry is None:
        return None

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
        *(str(note) for note in (entry.evidence_notes or [])),
        *(f"Reference: {url}" for url in (entry.references or [])),
    ]
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

    return {
        "overview": entry.root_cause,
        "causes": [entry.root_cause],
        "steps": steps,
        "evidence": evidence,
        "confidence": "high" if entry.resolution_status == "resolved" else "medium",
        "limitations": limitations,
    }
