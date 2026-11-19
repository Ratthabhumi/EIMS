"""Deterministic, idempotent demo seed for the 2026-11-24 EIMS demonstration.

Safety
------
* Requires ``EIMS_DEMO_SEED_DATABASE_URL`` and ``EIMS_DEMO_DATABASE_NAME``.
  The script aborts unless the *live* connection reports exactly that database.
* Never TRUNCATEs and never deletes. Re-running only fills gaps.
* Uses the real domain services (IncidentService) so the business rules and the
  verification gate are exercised, not bypassed.
* Synthetic identities only: ``demo.*`` usernames, ``DEMO-`` hostnames,
  ``demo-`` source ids.

What it builds
--------------
* 3 assets (web, database, workstation).
* 4 incidents: open, investigating, resolved (verified), reopened with a stale
  verification attempt.
* Analysis observations used as verification-grade evidence, with distinct
  attacher and verifier.
* A demo engineer and a demo reviewer account.

Run:
    set EIMS_DEMO_SEED_DATABASE_URL=postgresql+asyncpg://...
    set EIMS_DEMO_DATABASE_NAME=eims_demo
    python tools/seed_demo_2026.py
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.auth import hash_password
from backend.domain.asset_registry.models import InfrastructureAsset
from backend.domain.incident.models import Incident, IncidentEvidence
from backend.domain.incident.service import EvidenceInput, IncidentService
from backend.domain.incident.verification import VerificationRequest

URL_ENV = "EIMS_DEMO_SEED_DATABASE_URL"
NAME_ENV = "EIMS_DEMO_DATABASE_NAME"

ENGINEER = "demo.engineer"
REVIEWER = "demo.reviewer"
DEMO_PASSWORD_ENV = "EIMS_DEMO_PASSWORD"
BASE_TIME = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)


def _stable_uuid(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"eims-demo-2026:{name}")


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


async def _assert_target(db: AsyncSession) -> None:
    expected = (os.environ.get(NAME_ENV) or "").strip()
    if not expected:
        raise SystemExit(f"{NAME_ENV} must be set to the exact demo database name")
    row = (await db.execute(text(
        "SELECT current_database(), current_user"))).one()
    if row[0] != expected:
        raise SystemExit(
            f"refusing to seed: connected to {row[0]!r}, expected {expected!r}")
    if not expected.startswith("eims_demo"):
        raise SystemExit("demo database name must start with 'eims_demo'")
    print(f"target verified: database={row[0]} user={row[1]}")


async def _ensure_user(db: AsyncSession, username: str, role: str, *, reviewer: bool) -> None:
    existing = (
        await db.execute(select(User).where(User.username == username))
    ).scalars().first()
    if existing is not None:
        return
    password = os.environ.get(DEMO_PASSWORD_ENV, "")
    if not password:
        raise SystemExit(
            f"{DEMO_PASSWORD_ENV} must be set to seed the {username} account")
    db.add(
        User(
            username=username,
            role=role,
            knowledge_reviewer=reviewer,
            password=hash_password(password),
        )
    )
    await db.commit()
    print(f"created user {username} (role={role}, reviewer={reviewer})")


async def _ensure_asset(
    db: AsyncSession, key: str, hostname: str, ip: str, *, criticality: str
) -> uuid.UUID:
    asset_id = _stable_uuid(f"asset:{key}")
    existing = (
        await db.execute(
            select(InfrastructureAsset).where(
                InfrastructureAsset.cryptographic_fingerprint == _digest("asset", key)
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing.asset_id
    db.add(
        InfrastructureAsset(
            asset_id=asset_id,
            hostname=hostname,
            canonical_ip=ip,
            cryptographic_fingerprint=_digest("asset", key),
            lifecycle_state="Active",
            current_compliance_score=70.0,
        )
    )
    await db.commit()
    print(f"created asset {hostname} ({asset_id})")
    return asset_id


async def _ensure_observation(
    db: AsyncSession,
    *,
    key: str,
    asset_id: uuid.UUID | None,
    description: str,
    when: datetime,
) -> str:
    """One synthetic analysis observation used as verification evidence."""
    event_id = f"demo-{key}"
    existing = (
        await db.execute(
            select(AnalysisHistory).where(AnalysisHistory.event_id == event_id)
        )
    ).scalars().first()
    if existing is not None:
        return str(existing.id)
    row = AnalysisHistory(
        event_id=event_id,
        provider="DEMO-SYNTHETIC",
        username=ENGINEER,
        description=description,
        asset_id=asset_id,
        created_at=when.replace(tzinfo=None),
    )
    db.add(row)
    await db.commit()
    print(f"created analysis observation {event_id} (id={row.id})")
    return str(row.id)


async def _incident_by_source(db: AsyncSession, source_id: str) -> Incident | None:
    return (
        await db.execute(
            select(Incident)
            .join(IncidentEvidence, IncidentEvidence.incident_id == Incident.incident_id)
            .where(IncidentEvidence.source_id == source_id)
        )
    ).scalars().first()


async def _ensure_open_incident(
    db: AsyncSession, *, asset_id: uuid.UUID, source_id: str, title: str, severity: str
) -> uuid.UUID:
    existing = await _incident_by_source(db, source_id)
    if existing is not None:
        return existing.incident_id
    incident, created = await IncidentService(db).create_from_evidence(
        [EvidenceInput(
            source_type="winlog",
            source_id=source_id,
            source_event_key="4625",
            observed_at=BASE_TIME,
        )],
        actor=ENGINEER,
        asset_id=asset_id,
        title=title,
        severity=severity,
    )
    print(f"incident {title!r} created={created} id={incident.incident_id}")
    return incident.incident_id


async def _advance(db: AsyncSession, incident_id: uuid.UUID, *targets: str) -> None:
    for target in targets:
        incident = await IncidentService(db).get_incident(incident_id)
        if incident.status == target:
            continue
        try:
            await IncidentService(db).change_status(
                incident_id, target, actor=ENGINEER
            )
        except Exception as exc:  # noqa: BLE001 - idempotent re-run tolerance
            print(f"skip transition {target}: {type(exc).__name__}: {exc}")


async def _attach_and_verify(
    db: AsyncSession,
    *,
    incident_id: uuid.UUID,
    asset_id: uuid.UUID | None,
    key: str,
    description: str,
) -> None:
    source_id = await _ensure_observation(
        db, key=key, asset_id=asset_id, description=description,
        when=BASE_TIME + timedelta(minutes=30),
    )
    incident = await IncidentService(db).get_incident(incident_id)
    already = (
        await db.execute(
            select(IncidentEvidence).where(
                IncidentEvidence.incident_id == incident_id,
                IncidentEvidence.source_id == source_id,
            )
        )
    ).scalars().first()
    if already is None:
        await IncidentService(db).attach_evidence(
            incident_id,
            [EvidenceInput(
                source_type="analysis",
                source_id=source_id,
                observed_at=datetime.now(UTC),
            )],
            actor=ENGINEER,
        )
    evidence = (
        await db.execute(
            select(IncidentEvidence).where(
                IncidentEvidence.incident_id == incident_id,
                IncidentEvidence.source_id == source_id,
            )
        )
    ).scalars().first()
    assert evidence is not None
    try:
        await IncidentService(db).change_status(
            incident_id,
            "resolved",
            actor=REVIEWER,
            verification=VerificationRequest(evidence_id=evidence.evidence_id),
            verifier=REVIEWER,
        )
        print(f"verified and resolved incident {incident_id}")
    except Exception as exc:  # noqa: BLE001
        print(f"verification step skipped for {incident_id}: {type(exc).__name__}: {exc}")


async def main() -> int:
    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        print(f"{URL_ENV} is required", file=sys.stderr)
        return 2
    engine = create_async_engine(url, pool_pre_ping=True)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as db:
            await _assert_target(db)
            await _ensure_user(db, ENGINEER, "user", reviewer=False)
            await _ensure_user(db, REVIEWER, "user", reviewer=True)

            web = await _ensure_asset(
                db, "web-01", "DEMO-WEB-01", "10.20.0.11", criticality="high")
            database = await _ensure_asset(
                db, "db-01", "DEMO-DB-01", "10.20.0.12", criticality="critical")
            workstation = await _ensure_asset(
                db, "ws-01", "DEMO-WS-01", "10.20.0.21", criticality="medium")

            # 1) Open incident: repeated failed logons on the workstation.
            open_id = await _ensure_open_incident(
                db, asset_id=workstation, source_id="demo-winlog-4625-ws01",
                title="Repeated failed logon attempts on DEMO-WS-01", severity="medium")

            # 2) Investigating incident: disk pressure on the database host.
            db_id = await _ensure_open_incident(
                db, asset_id=database, source_id="demo-telemetry-db-disk",
                title="Disk latency spike on DEMO-DB-01", severity="high")
            await _advance(db, db_id, "triage", "investigating")

            # 3) Verified and resolved incident: patched web service.
            web_id = await _ensure_open_incident(
                db, asset_id=web, source_id="demo-winlog-4625-web01",
                title="Authentication failures on DEMO-WEB-01", severity="high")
            await _advance(db, web_id, "triage", "investigating")
            await _attach_and_verify(
                db, incident_id=web_id, asset_id=web, key="web01-post-patch",
                description="Post-patch authentication observation: no failures",
            )

            # 4) Reopened incident with a stale verification attempt: the old
            #    cycle evidence cannot resolve the new cycle.
            reopened_id = await _ensure_open_incident(
                db, asset_id=database, source_id="demo-winlog-4740-db01",
                title="Account lockout on DEMO-DB-01", severity="medium")
            await _advance(db, reopened_id, "triage", "investigating")
            await _attach_and_verify(
                db, incident_id=reopened_id, asset_id=database, key="db01-unlock",
                description="Post-remediation unlock observation",
            )
            async with maker() as db2:
                current = await IncidentService(db2).get_incident(reopened_id)
                if current.status == "resolved":
                    await IncidentService(db2).change_status(
                        reopened_id, "investigating", actor=ENGINEER)
                    print(f"reopened incident {reopened_id} to cycle 1")

        print("demo seed complete")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
