"""Provider isolation of approved Knowledge (real PostgreSQL, disposable database).

Contract: an approved entry for a provider-bearing family (Windows events) is only an exact match for the SAME
provider. Legacy rows without a provider are ``unknown`` and never match; explicit ``generic`` entries are contextual;
vendor-unique families (Cisco, Fortinet, ...) keep matching by family + code. Provider scope survives proposal ->
review -> retrieval, and nothing infers a provider from an Event ID.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from backend.api.routers.analyzer.knowledge import (
    KnowledgeProposalRequest,
    KnowledgeReviewRequest,
    create_knowledge_proposal,
    review_knowledge,
)
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.models.knowledge import KnowledgeEntry
from backend.domain.analyzer.services.verified_knowledge import derive_provider_scope, search_approved_knowledge
from tests.incident_db_support import create_schema, require_database_url, session_factory


def _entry(history_id, identity="1000", family="windows_event", provider=None, scope="unknown", root="root", status="approved",
           lifecycle="active"):
    return KnowledgeEntry(
        source_history_id=history_id, source_history_hash="h" * 64, source_family=family, diagnostic_identity=identity,
        provider=provider, provider_scope=scope, title="t " + root, resolution_status="resolved", root_cause=root,
        solution_steps=["do something"], evidence_notes=["note"], references=[], status=status, proposed_by="proposer",
        reviewed_by="reviewer" if status == "approved" else None, reviewed_at=datetime.now(UTC) if status == "approved" else None,
        lifecycle_state=lifecycle)


async def _world(url):
    schema, engine = await create_schema(url)
    maker = session_factory(engine)
    async with maker() as db:
        rows = []
        for n in range(12):
            rows.append(AnalysisHistory(event_id="1000", provider="Application Error", username="synthetic", description=f"d{n}"))
        db.add_all(rows)
        await db.commit()
        return engine, maker, [r.id for r in rows]


def _run(coro_fn):
    url = require_database_url()

    async def go():
        engine, maker, ids = await _world(url)
        try:
            await coro_fn(maker, ids)
        finally:
            await engine.dispose()

    asyncio.run(go())


def test_same_event_id_different_providers_are_isolated():
    async def body(maker, ids):
        async with maker() as db:
            db.add_all([_entry(ids[0], provider="Application Error", scope="provider_specific", root="APP ERROR cause"),
                        _entry(ids[1], provider=".NET Runtime", scope="provider_specific", root="DOTNET cause")])
            await db.commit()
        async with maker() as db:
            a = await search_approved_knowledge(db, "windows_event", "1000", "Application Error")
            b = await search_approved_knowledge(db, "windows_event", "1000", ".net runtime")
            c = await search_approved_knowledge(db, "windows_event", "1000", "Some Other Provider")
        assert a["overview"] == "APP ERROR cause" and b["overview"] == "DOTNET cause"
        assert c is None  # provider B asked, provider C entry absent: nothing is borrowed from A or B
    _run(body)


def test_provider_a_entry_is_not_returned_for_provider_b_or_missing_provider():
    async def body(maker, ids):
        async with maker() as db:
            db.add(_entry(ids[0], provider="Application Error", scope="provider_specific"))
            await db.commit()
        async with maker() as db:
            assert await search_approved_knowledge(db, "windows_event", "1000", ".NET Runtime") is None
            assert await search_approved_knowledge(db, "windows_event", "1000", "") is None
            assert await search_approved_knowledge(db, "windows_event", "1000", None) is None
            assert await search_approved_knowledge(db, "windows_event", "1000", "unknown") is None
    _run(body)


def test_legacy_unknown_provider_entry_never_matches_a_provider_bearing_family():
    async def body(maker, ids):
        async with maker() as db:
            db.add(_entry(ids[0], scope="unknown", root="legacy"))
            db.add(_entry(ids[1], scope="unverified", provider="Maybe", root="doubtful"))
            await db.commit()
        async with maker() as db:
            for provider in ("Application Error", "", None, "Maybe"):
                assert await search_approved_knowledge(db, "windows_event", "1000", provider) is None
    _run(body)


def test_explicit_generic_entry_is_contextual_and_loses_to_provider_exact():
    async def body(maker, ids):
        async with maker() as db:
            db.add(_entry(ids[0], scope="generic", root="GENERIC"))
            await db.commit()
        async with maker() as db:
            hit = await search_approved_knowledge(db, "windows_event", "1000", "Whatever")
        assert hit["overview"] == "GENERIC" and hit["confidence"] == "medium"
        assert any("Contextual match only" in text_ for text_ in hit["limitations"])
        assert any("generic_context" in text_ for text_ in hit["evidence"])
        async with maker() as db:
            db.add(_entry(ids[1], provider="Whatever", scope="provider_specific", root="EXACT"))
            await db.commit()
        async with maker() as db:
            hit = await search_approved_knowledge(db, "windows_event", "1000", "Whatever")
            other = await search_approved_knowledge(db, "windows_event", "1000", "Else")
        assert hit["overview"] == "EXACT" and hit["confidence"] == "high"
        assert other["overview"] == "GENERIC"  # other providers only ever see the contextual entry
    _run(body)


def test_conflicting_provider_specific_entries_without_caller_provider_select_nothing():
    async def body(maker, ids):
        async with maker() as db:
            db.add_all([_entry(ids[0], provider="Provider X", scope="provider_specific", root="X"),
                        _entry(ids[1], provider="Provider Y", scope="provider_specific", root="Y")])
            await db.commit()
        async with maker() as db:
            assert await search_approved_knowledge(db, "windows_event", "1000", "") is None
    _run(body)


def test_vendor_product_and_non_windows_retrieval_stay_compatible():
    async def body(maker, ids):
        async with maker() as db:
            db.add_all([_entry(ids[0], identity="FGT-1", family="fortinet", scope="vendor_product", root="forti"),
                        _entry(ids[1], identity="106023", family="cisco_asa", scope="unknown", root="cisco legacy")])
            await db.commit()
        async with maker() as db:
            assert (await search_approved_knowledge(db, "fortinet", "FGT-1", "anything"))["overview"] == "forti"
            assert (await search_approved_knowledge(db, "fortinet", "FGT-1"))["overview"] == "forti"
            assert (await search_approved_knowledge(db, "cisco_asa", "106023"))["overview"] == "cisco legacy"
            assert await search_approved_knowledge(db, "cisco_asa", "FGT-1") is None  # never across families
    _run(body)


def test_stale_pending_and_withdrawn_entries_are_never_returned():
    async def body(maker, ids):
        async with maker() as db:
            db.add_all([
                _entry(ids[0], provider="P", scope="provider_specific", lifecycle="revalidation_required"),
                _entry(ids[1], provider="P", scope="provider_specific", status="pending"),
                _entry(ids[2], provider="P", scope="provider_specific", lifecycle="withdrawn"),
            ])
            await db.commit()
        async with maker() as db:
            assert await search_approved_knowledge(db, "windows_event", "1000", "P") is None
    _run(body)


def test_db_rejects_provider_specific_without_provider_and_unknown_scope_values():
    async def body(maker, ids):
        from sqlalchemy.exc import IntegrityError
        for bad in (_entry(ids[0], provider=None, scope="provider_specific"), _entry(ids[1], provider="  ", scope="provider_specific"),
                    _entry(ids[2], provider="P", scope="nonsense")):
            async with maker() as db:
                db.add(bad)
                with pytest.raises(IntegrityError):
                    await db.commit()
    _run(body)


def _proposal(history_id, **extra):
    return KnowledgeProposalRequest(
        history_id=history_id, title="Provider scoped fix", resolution_status="resolved", root_cause="A documented root cause",
        solution_steps=["Apply the documented step"], evidence_notes=["Observed in log"], **extra)


def test_proposal_review_approval_preserves_provider_scope_and_never_infers_from_event_id():
    async def body(maker, ids):
        async with maker() as db:
            known = AnalysisHistory(event_id="1000", provider="Application Error", username="eng", description="x",
                                    event_metadata={"sourceFamily": "windows_event"})
            none = AnalysisHistory(event_id="1000", provider="", username="eng", description="y",
                                   event_metadata={"sourceFamily": "windows_event"})
            db.add_all([known, none])
            await db.commit()
            ids_ = (known.id, none.id)
        async with maker() as db:
            entry = await create_knowledge_proposal(db, _proposal(ids_[0]), "eng")
            assert (entry.provider, entry.provider_scope, entry.status) == ("Application Error", "provider_specific", "pending")
            kid = entry.id
        async with maker() as db:
            # A pending proposal is never retrievable.
            assert await search_approved_knowledge(db, "windows_event", "1000", "Application Error") is None
            await review_knowledge(kid, KnowledgeReviewRequest(decision="approve", note="reviewed ok"), db, "reviewer")
        async with maker() as db:
            assert (await search_approved_knowledge(db, "windows_event", "1000", "Application Error")) is not None
            assert await search_approved_knowledge(db, "windows_event", "1000", ".NET Runtime") is None
            row = await db.get(KnowledgeEntry, kid)
            assert (row.provider, row.provider_scope) == ("Application Error", "provider_specific")
        # Provider missing on the analysed record: recorded as unknown, approval refused (it could never match).
        async with maker() as db:
            entry2 = await create_knowledge_proposal(db, _proposal(ids_[1]), "eng")
            assert (entry2.provider, entry2.provider_scope) == (None, "unknown")
            with pytest.raises(HTTPException) as err:
                await review_knowledge(entry2.id, KnowledgeReviewRequest(decision="approve", note="reviewed ok"), db, "reviewer")
            assert err.value.status_code == 422 and "Provider attribution" in err.value.detail
    _run(body)


def test_derive_provider_scope_rules():
    assert derive_provider_scope("windows_event", "Application Error") == ("Application Error", "provider_specific")
    assert derive_provider_scope("windows_event", "") == (None, "unknown")
    assert derive_provider_scope("windows_event", "Unknown") == (None, "unknown")
    assert derive_provider_scope("windows_event", "Application Error", "generic") == (None, "generic")
    assert derive_provider_scope("cisco_asa", "") == (None, "vendor_product")
    assert derive_provider_scope("fortinet", "x")[1] == "vendor_product"


def test_migration_defaults_existing_rows_to_unknown_without_inventing_a_provider():
    url = require_database_url()

    async def go():
        from alembic import command
        from alembic.config import Config
        from tests.test_knowledge_overlay_pg import _create_schema, _migrate

        schema, engine = _create_schema(url)
        try:
            await _migrate(engine, schema)

            def run(direction, target):
                def go_(connection):
                    cfg = Config()
                    cfg.set_main_option("script_location", "migrations")
                    cfg.attributes.update(connection=connection, version_table_schema=schema)
                    (command.downgrade if direction == "down" else command.upgrade)(cfg, target)
                return go_

            async with engine.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                await conn.commit()
                await conn.run_sync(run("down", "a7d2c5e8f604"))
                await conn.commit()
                cols = set((await conn.execute(text(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema=:s AND table_name='knowledge_entries'"),
                    {"s": schema})).scalars())
                assert "provider" not in cols and "provider_scope" not in cols
                await conn.rollback()
            async with engine.connect() as conn:
                await conn.execute(text(f'SET search_path TO "{schema}", public'))
                await conn.commit()
                await conn.run_sync(run("up", "head"))
                await conn.commit()
                row = (await conn.execute(text(
                    "SELECT column_default, is_nullable FROM information_schema.columns WHERE table_schema=:s AND "
                    "table_name='knowledge_entries' AND column_name='provider_scope'"), {"s": schema})).one()
                assert "unknown" in row[0] and row[1] == "NO"
                await conn.rollback()
        finally:
            await engine.dispose()

    asyncio.run(go())
