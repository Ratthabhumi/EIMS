"""Knowledge retrieval against a real disposable PostgreSQL overlay."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from backend.domain.analyzer.services.operational_catalog import get_catalog
from backend.domain.knowledge.models import KnowledgeReview, KnowledgeReviewEvent
from backend.domain.knowledge.retrieval import retrieve
from backend.domain.knowledge.service import promote, resolve_catalog, sync
from tests.incident_db_support import (
    INCIDENT_TABLES,
    create_schema,
    require_database_url,
    session_factory,
)
from tests.test_knowledge_service import SOURCE, VALID, _trigger_ddl


def _diag_entry() -> dict:
    cid = next(e["catalog_id"] for e in resolve_catalog()
               if e["knowledge_class"] == "diagnostic_candidate")
    return next(e for e in get_catalog() if e["catalog_id"] == cid)


async def _engine(url, tables):
    _schema, engine = await create_schema(url, tables=tables)
    mod = _trigger_ddl()
    if KnowledgeReviewEvent.__table__ in tables:
        async with engine.begin() as conn:
            for ddl in (mod.APPEND_ONLY_FUNCTION_DDL, mod.APPEND_ONLY_TRIGGER_DDL,
                        mod.APPEND_ONLY_TRUNCATE_DDL):
                await conn.execute(text(ddl))
    return engine


def test_retrieval_follows_the_real_lifecycle_and_stale_downgrade():
    url = require_database_url()
    tables = list(INCIDENT_TABLES) + [KnowledgeReview.__table__, KnowledgeReviewEvent.__table__]

    async def scenario():
        engine = await _engine(url, tables)
        try:
            entry = _diag_entry()
            cid = entry["catalog_id"]
            async with session_factory(engine)() as db:
                assert (await retrieve(db, entry))["classification"] == "diagnostic_candidate_match"
                await promote(db, cid, "source_verified", actor="alice", actor_kind="human", rationale="r", review=SOURCE)
                await db.commit()
            async with session_factory(engine)() as db:
                assert (await retrieve(db, entry))["classification"] == "source_verified_match"
                await promote(db, cid, "validated", actor="bob", actor_kind="human", rationale="r", review=VALID)
                await db.commit()
            async with session_factory(engine)() as db:
                assert (await retrieve(db, entry))["classification"] == "validated_diagnostic_match"
                await promote(db, cid, "approved", actor="carol", actor_kind="human", rationale="r")
                await promote_scope(db, cid)
                await db.commit()
            async with session_factory(engine)() as db:
                assert (await retrieve(db, entry))["classification"] == "approved_diagnostic_match"
                ok = await retrieve(db, entry, detected_version="12.1")
                assert ok["classification"] == "version_compatible_match"
                bad = await retrieve(db, entry, detected_version="11.0")
                assert bad["classification"] == "no_verified_match"
                # content drift -> stale -> trust is withdrawn immediately
                await db.execute(text("UPDATE knowledge_review SET review_required = true"))
                await db.commit()
            async with session_factory(engine)() as db:
                stale = await retrieve(db, entry, detected_version="12.1")
                assert stale["classification"] == "diagnostic_candidate_match"
                assert stale["stale"] is True
        finally:
            await engine.dispose()

    asyncio.run(scenario())


async def promote_scope(db, cid):
    await db.execute(text("UPDATE knowledge_review SET product_version_scope = 'Product 12.x' "
                          "WHERE catalog_id = :c"), {"c": cid})


def test_missing_overlay_fails_closed_without_poisoning_the_transaction():
    url = require_database_url()

    async def scenario():
        engine = await _engine(url, list(INCIDENT_TABLES))  # no knowledge tables
        try:
            async with session_factory(engine)() as db:
                result = await retrieve(db, _diag_entry())
                assert result["classification"] == "diagnostic_candidate_match"
                assert result["overlayAvailable"] is False
                # the caller's transaction must still be usable (history insert follows)
                assert (await db.execute(text("SELECT 1"))).scalar() == 1
        finally:
            await engine.dispose()

    asyncio.run(scenario())
