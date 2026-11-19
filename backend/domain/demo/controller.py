"""Read-only demo surface for the internal EIMS presentation.

Enabled only when ``EIMS_DEMO_PUBLIC_ACCESS=1``. It is deliberately narrow:

* no authentication is required, so the boundary is enforced here, not in the UI;
* the live connection must report the dedicated demo database, otherwise the
  whole router fails closed;
* every endpoint is read-only. Resolution/verification stay behind the normal
  authenticated API and the existing DB triggers, so the demo can *show* a
  verified resolution but cannot forge one;
* only synthetic demo tables are exposed: no users, no password hashes, no
  admin surface, no arbitrary SQL.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.asset_registry.models import AuditLog, InfrastructureAsset
from backend.domain.incident.models import Incident, IncidentEvidence, IncidentVerification
from backend.infrastructure.database import get_db_session
from backend.infrastructure.db_identity import connection_identity

DEMO_FLAG = "EIMS_DEMO_PUBLIC_ACCESS"
DEMO_DATABASE_PREFIX = "eims_demo"

demo_router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])


async def require_demo_scope(db: AsyncSession = Depends(get_db_session)) -> None:
    """Fail closed unless this process is an explicitly enabled demo instance."""
    if (os.environ.get(DEMO_FLAG) or "").strip() != "1":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    identity = await connection_identity(db)
    if not (identity.database or "").startswith(DEMO_DATABASE_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Demo access is not available on this database",
        )


@demo_router.get("/summary", dependencies=[Depends(require_demo_scope)])
async def demo_summary(db: AsyncSession = Depends(get_db_session)) -> dict:
    async def count(stmt) -> int:
        return int((await db.execute(stmt)).scalar() or 0)

    resolved = await count(select(func.count()).select_from(Incident).where(Incident.status == "resolved"))
    investigating = await count(
        select(func.count()).select_from(Incident).where(Incident.status == "investigating")
    )
    open_count = await count(select(func.count()).select_from(Incident).where(Incident.status == "open"))
    return {
        "database": (await connection_identity(db)).database,
        "assets": await count(select(func.count()).select_from(InfrastructureAsset)),
        "observations": await count(select(func.count()).select_from(AnalysisHistory)),
        "incidents": {
            "open": open_count,
            "investigating": investigating,
            "resolved": resolved,
            "total": open_count + investigating + resolved,
        },
        "evidence": await count(select(func.count()).select_from(IncidentEvidence)),
        "verifications": await count(select(func.count()).select_from(IncidentVerification)),
        "audit_rows": await count(select(func.count()).select_from(AuditLog)),
        "demo_access": "public-read-only",
    }


@demo_router.get("/assets", dependencies=[Depends(require_demo_scope)])
async def demo_assets(db: AsyncSession = Depends(get_db_session)) -> dict:
    rows = (await db.execute(
        select(InfrastructureAsset).order_by(InfrastructureAsset.hostname)
    )).scalars().all()
    incidents = (await db.execute(select(Incident))).scalars().all()
    by_asset: dict[str, list[dict]] = {}
    for inc in incidents:
        if inc.asset_id:
            by_asset.setdefault(str(inc.asset_id), []).append(
                {"incident_id": str(inc.incident_id), "title": inc.title, "status": inc.status}
            )
    return {
        "data": [
            {
                "asset_id": str(a.asset_id),
                "hostname": a.hostname,
                "canonical_ip": a.canonical_ip,
                "lifecycle_state": getattr(a, "lifecycle_state", None),
                "compliance_score": getattr(a, "current_compliance_score", None),
                "incidents": by_asset.get(str(a.asset_id), []),
            }
            for a in rows
        ]
    }


@demo_router.get("/observations", dependencies=[Depends(require_demo_scope)])
async def demo_observations(db: AsyncSession = Depends(get_db_session)) -> dict:
    rows = (await db.execute(
        select(AnalysisHistory).order_by(AnalysisHistory.id.desc()).limit(100)
    )).scalars().all()
    return {
        "data": [
            {
                "id": r.id,
                "event_id": r.event_id,
                "provider": r.provider,
                "username": r.username,
                "description": r.description,
                "asset_id": str(r.asset_id) if r.asset_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "note": "Pre-seeded analysis observations. Live ingestion is not running in this demo.",
    }


@demo_router.get("/incidents", dependencies=[Depends(require_demo_scope)])
async def demo_incidents(db: AsyncSession = Depends(get_db_session)) -> dict:
    rows = (await db.execute(select(Incident).order_by(Incident.last_seen.desc()))).scalars().all()
    evidence_counts = dict((await db.execute(
        select(IncidentEvidence.incident_id, func.count()).group_by(IncidentEvidence.incident_id)
    )).all())
    verif_counts = dict((await db.execute(
        select(IncidentVerification.incident_id, func.count()).group_by(IncidentVerification.incident_id)
    )).all())
    assets = {str(a.asset_id): a.hostname for a in (await db.execute(select(InfrastructureAsset))).scalars().all()}
    return {
        "data": [
            {
                "incident_id": str(i.incident_id),
                "title": i.title,
                "severity": i.severity,
                "status": i.status,
                "confidence": i.confidence,
                "root_cause_state": i.root_cause_state,
                "asset": assets.get(str(i.asset_id)) if i.asset_id else None,
                "first_seen": i.first_seen.isoformat() if i.first_seen else None,
                "last_seen": i.last_seen.isoformat() if i.last_seen else None,
                "remediation_cycle": i.remediation_cycle,
                "evidence_count": int(evidence_counts.get(i.incident_id, 0)),
                "verification_count": int(verif_counts.get(i.incident_id, 0)),
                "guidance": (i.summary or {}).get("demo_guidance"),
            }
            for i in rows
        ]
    }


@demo_router.get("/incidents/{incident_id}", dependencies=[Depends(require_demo_scope)])
async def demo_incident(incident_id: str, db: AsyncSession = Depends(get_db_session)) -> dict:
    import uuid as _uuid

    try:
        key = _uuid.UUID(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    incident = (await db.execute(select(Incident).where(Incident.incident_id == key))).scalars().first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Not found")
    evidence = (await db.execute(
        select(IncidentEvidence).where(IncidentEvidence.incident_id == key)
        .order_by(IncidentEvidence.created_at)
    )).scalars().all()
    verifications = (await db.execute(
        select(IncidentVerification).where(IncidentVerification.incident_id == key)
        .order_by(IncidentVerification.verified_at)
    )).scalars().all()
    asset = None
    if incident.asset_id:
        row = (await db.execute(
            select(InfrastructureAsset).where(InfrastructureAsset.asset_id == incident.asset_id)
        )).scalars().first()
        asset = row.hostname if row else None
    return {
        "incident": {
            "incident_id": str(incident.incident_id),
            "title": incident.title,
            "severity": incident.severity,
            "status": incident.status,
            "confidence": incident.confidence,
            "root_cause_state": incident.root_cause_state,
            "asset": asset,
            "first_seen": incident.first_seen.isoformat() if incident.first_seen else None,
            "last_seen": incident.last_seen.isoformat() if incident.last_seen else None,
            "remediation_cycle": incident.remediation_cycle,
            "correlation": (incident.summary or {}).get("correlation"),
            "guidance": (incident.summary or {}).get("demo_guidance"),
        },
        "evidence": [
            {
                "evidence_id": str(e.evidence_id),
                "source_type": e.source_type,
                "source_id": e.source_id,
                "digest": e.evidence_digest,
                "observed_at": e.observed_at.isoformat() if e.observed_at else None,
                "added_by": e.added_by,
            }
            for e in evidence
        ],
        "verifications": [
            {
                "verification_id": str(v.verification_id),
                "remediation_cycle": v.remediation_cycle,
                "outcome": v.outcome,
                "verifier_id": v.verifier_id,
                "verified_at": v.verified_at.isoformat() if v.verified_at else None,
                "evidence_id": str(v.evidence_id),
            }
            for v in verifications
        ],
    }
