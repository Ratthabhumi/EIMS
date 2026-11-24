"""Knowledge service: resolve, sparse sync, hash invalidation, lifecycle, summary."""
from tests import catalog_expectations as X
import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text

from backend.domain.knowledge.models import KnowledgeReview, KnowledgeReviewEvent
from backend.domain.knowledge.service import (
    KnowledgePermissionError,
    KnowledgeTransitionRejected,
    canonical_hash,
    history,
    promote,
    resolve_catalog,
    summary,
    sync,
)
from backend.infrastructure.database import Base
from tests.incident_db_support import (
    INCIDENT_TABLES,
    create_schema,
    require_database_url,
    session_factory,
)

TABLES = list(INCIDENT_TABLES) + [KnowledgeReview.__table__, KnowledgeReviewEvent.__table__]


def _trigger_ddl() -> None:
    path = (Path(__file__).resolve().parents[1] / "migrations" / "versions"
            / "a1c4e7b9d201_add_knowledge_review.py")
    spec = importlib.util.spec_from_file_location("_knowledge_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def pg():
    url = require_database_url()
    engine = asyncio.run(_make(url))
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


async def _make(url):
    _schema, engine = await create_schema(url, tables=TABLES)
    mod = _trigger_ddl()
    async with engine.begin() as conn:
        for ddl in (mod.APPEND_ONLY_FUNCTION_DDL, mod.APPEND_ONLY_TRIGGER_DDL,
                    mod.APPEND_ONLY_TRUNCATE_DDL):
            await conn.execute(text(ddl))
    return engine


def test_resolve_catalog_with_class_defaults():
    entries = resolve_catalog()
    assert len(entries) == X.TOTAL
    context = [e for e in entries if e["knowledge_class"] == "operational_context"]
    diag = [e for e in entries if e["knowledge_class"] == "diagnostic_candidate"]
    assert len(context) == 153
    assert len(diag) == X.VENDOR_COUNT
    assert all(e["default_lifecycle"] == "not_applicable" for e in context)
    assert all(e["default_lifecycle"] == "candidate" for e in diag)
    assert len({e["catalog_id"] for e in entries}) == X.TOTAL


def test_sync_is_idempotent_and_detects_one_change(pg):
    async def scenario():
        async with session_factory(pg)() as db:
            first = (await db.execute(select(KnowledgeReview))).scalars().first()
            assert first is None  # sparse: nothing created by resolve
            entry = resolve_catalog()[0]
            db.add(KnowledgeReview(
                catalog_id=entry["catalog_id"], catalog_source="operational",
                content_hash="0" * 64, lifecycle_status="candidate", revision=1,
            ))
            await db.commit()

            await sync(db)
            await db.commit()
            events = (await db.execute(select(KnowledgeReviewEvent))).scalars().all()
            assert len(events) == 1
            assert events[0].event_type == "review_required"

            await sync(db)  # unchanged -> no new event
            await db.commit()
            events = (await db.execute(select(KnowledgeReviewEvent))).scalars().all()
            assert len(events) == 1

            row = (await db.execute(select(KnowledgeReview))).scalars().first()
            assert row.review_required is True
            assert row.content_hash == canonical_hash(
                next(e for e in _catalog_raw() if e["catalog_id"] == entry["catalog_id"]))

    asyncio.run(scenario())


def _catalog_raw():
    from backend.domain.analyzer.services.operational_catalog import load_catalog
    return load_catalog()


SOURCE = {
    "source_title": "Vendor KB", "source_url": "https://vendor.example/kb1",
    "supporting_section": "Cause", "claim_evidence": "States the failure mode.",
    "verified_at": "2026-11-19T10:00:00+00:00", "verifier": "alice",
    "vendor_product_scope": "Product 12",
}
VALID = {
    "product_version_scope": "Product 12.x", "applicability": "VMware jobs",
    "validation_basis": "Lab run 1", "verification_criteria": ["job completes"],
}


def test_promotion_rejects_invalid_and_self_approval(pg):
    async def scenario():
        diag = next(e for e in resolve_catalog()
                    if e["knowledge_class"] == "diagnostic_candidate")
        cid = diag["catalog_id"]
        async with session_factory(pg)() as db:
            with pytest.raises(KnowledgeTransitionRejected):
                await promote(db, cid, "approved", actor="alice", actor_kind="human", rationale="skip gates")
            await db.rollback()

        # an incomplete source_verified is refused and leaves no row and no event
        async with session_factory(pg)() as db:
            with pytest.raises(KnowledgeTransitionRejected, match="source_title"):
                await promote(db, cid, "source_verified", actor="alice", actor_kind="human",
                              rationale="x", review={**SOURCE, "source_title": ""})
            await db.rollback()
        async with session_factory(pg)() as db:
            assert (await db.execute(select(KnowledgeReview))).scalars().first() is None
            assert await history(db, cid) == []

        async with session_factory(pg)() as db:
            await promote(db, cid, "source_verified", actor="alice", actor_kind="human",
                          rationale="source inspected", review=SOURCE)
            await db.commit()
        async with session_factory(pg)() as db:
            await promote(db, cid, "validated", actor="bob", actor_kind="human",
                          rationale="lab validation", review=VALID)
            await db.commit()
        # separation of duties: neither verifier nor validator may approve
        for actor in ("alice", "bob"):
            async with session_factory(pg)() as db:
                with pytest.raises(KnowledgePermissionError):
                    await promote(db, cid, "approved", actor=actor, actor_kind="human", rationale="ship it")
                await db.rollback()
        async with session_factory(pg)() as db:
            with pytest.raises(KnowledgePermissionError):
                await promote(db, cid, "approved", actor="carol", actor_kind="human",
                              rationale="ship it", contributor="carol")
            await db.rollback()

        async with session_factory(pg)() as db:
            row = await promote(db, cid, "approved", actor="carol", actor_kind="human",
                                rationale="independent approval", contributor="bob")
            await db.commit()
            assert row.lifecycle_status == "approved"
            events = await history(db, cid)
            assert [e["to_status"] for e in events] == [
                "source_verified", "validated", "approved"]
            assert events[0]["evidence"]["source_url"] == SOURCE["source_url"]

    asyncio.run(scenario())


def test_ai_or_automation_actor_cannot_record_a_decision_and_actor_kind_is_persisted(pg):
    async def scenario():
        diag = next(e for e in resolve_catalog() if e["knowledge_class"] == "diagnostic_candidate")
        cid = diag["catalog_id"]
        for kind in ("ai_assist", "automation", None):
            async with session_factory(pg)() as db:
                with pytest.raises(KnowledgePermissionError, match="human decision"):
                    await promote(db, cid, "source_verified", actor="agent-1", actor_kind=kind, rationale="read the page", review=SOURCE)
                await db.rollback()
        async with session_factory(pg)() as db:
            assert (await db.execute(select(KnowledgeReview))).scalars().first() is None  # nothing was written
            assert await history(db, cid) == []
        async with session_factory(pg)() as db:
            await promote(db, cid, "source_verified", actor="alice", actor_kind="human", rationale="source inspected", review=SOURCE)
            await db.commit()
        async with session_factory(pg)() as db:
            events = await history(db, cid)
            assert events[0]["evidence"]["actor_kind"] == "human" and events[0]["actor"] == "alice"

    asyncio.run(scenario())


def test_summary_excludes_stale_from_trusted_counts(pg):
    async def scenario():
        diag = next(e for e in resolve_catalog()
                    if e["knowledge_class"] == "diagnostic_candidate")
        async with session_factory(pg)() as db:
            db.add(KnowledgeReview(
                catalog_id=diag["catalog_id"], catalog_source="diagnostic",
                content_hash="f" * 64, lifecycle_status="approved",
                review_required=True, revision=3,
            ))
            await db.commit()
        async with session_factory(pg)() as db:
            data = await summary(db)
        assert data["counts"]["approved"] == 0, "stale approval must not count"
        assert data["counts"]["stale_review"] == 1
        assert data["counts"]["operational_context"] == 153
        assert data["counts"]["diagnostic_candidates"] == X.VENDOR_COUNT
        assert data["counts"]["overlay_rows"] == 1

    asyncio.run(scenario())
