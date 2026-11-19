"""Outbox dispatcher: claim (short DB tx) -> XADD (no DB tx) -> stamp (short, network-free DB tx).

A crash between XADD and the stamp republishes the row (at-least-once). The consumer is idempotent.
"""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError
from sqlalchemy import exists, update
from sqlalchemy.future import select

from backend.core.logger import get_logger
from backend.domain.incident.models import IncidentEvidence
from backend.domain.incident_ingest.envelope import (
    INGEST_DEAD_LETTER_KEY, INGEST_STREAM_KEY, EnvelopeError, IngestEnvelope,
)
from backend.domain.incident_ingest.models import IncidentIngestOutbox

logger = get_logger("eims.incident_ingest.dispatcher")
DISPATCH_BATCH = 100


def _envelope_from_row(row: IncidentIngestOutbox) -> IngestEnvelope:
    return IngestEnvelope(
        outbox_id=row.outbox_id, source_type=row.source_type, source_id=row.source_id,
        observed_at=row.observed_at, source_event_key=row.source_event_key,
        asset_id=row.asset_id, provenance=dict(row.provenance or {}))


async def dispatch_pending(session_maker, redis_client, limit: int = DISPATCH_BATCH) -> int:
    """Publish pending outbox rows; returns the number published and stamped.

    Redis down / unconfirmed XADD leaves the row pending. Rows are claimed with
    FOR UPDATE SKIP LOCKED but locks are released before Redis I/O, so concurrent dispatchers may
    publish the same row; downstream idempotency absorbs that.
    """
    if session_maker is None or redis_client is None:
        return 0
    async with session_maker() as session:
        async with session.begin():
            result = await session.execute(
                select(IncidentIngestOutbox)
                .where(IncidentIngestOutbox.published_at.is_(None))
                .order_by(IncidentIngestOutbox.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True))
            claimed: list[tuple] = []
            for row in result.scalars().all():
                try:
                    claimed.append((row.outbox_id, _envelope_from_row(row).to_stream_fields()))
                except EnvelopeError as exc:
                    # Cannot happen through enqueue (same validators + CHECK constraints); never block siblings.
                    logger.error("Outbox row %s is not publishable (%s); left pending", row.outbox_id, exc)

    published = 0
    for outbox_id, fields in claimed:
        try:
            stream_id = await redis_client.xadd(INGEST_STREAM_KEY, fields)
        except (RedisError, OSError, asyncio.TimeoutError) as exc:
            logger.error("Incident-ingest XADD failed (%s); outbox row stays pending", type(exc).__name__)
            break
        if not stream_id:
            logger.error("Incident-ingest XADD unconfirmed; outbox row stays pending")
            break
        # Stamp only after a confirmed XADD, in a separate transaction with no network awaits.
        async with session_maker() as stamp_session:
            async with stamp_session.begin():
                await stamp_session.execute(
                    update(IncidentIngestOutbox)
                    .where(IncidentIngestOutbox.outbox_id == outbox_id)
                    .where(IncidentIngestOutbox.published_at.is_(None))
                    .values(published_at=datetime.now(UTC)))
        published += 1
    return published


async def reconcile_published_without_evidence(
        session_maker, *, older_than_seconds: int = 300, limit: int = 100) -> int:
    """Operator-invoked (never automatic): re-arm published outbox rows that have no incident_evidence.

    Covers a Redis stream loss / DLQ'd entry whose incident never committed. Re-arming only clears
    ``published_at``; the single dispatcher republishes and the idempotent sink absorbs any duplicate.
    A row whose entry is genuinely poison will be re-armed again by the next run: fix or purge the
    cause first. Returns the number of rows re-armed. Never deletes anything.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=max(0, older_than_seconds))
    async with session_maker() as session:
        async with session.begin():
            stale = (
                select(IncidentIngestOutbox.outbox_id)
                .where(IncidentIngestOutbox.published_at.is_not(None))
                .where(IncidentIngestOutbox.published_at < cutoff)
                .where(~exists().where(
                    IncidentEvidence.source_type == IncidentIngestOutbox.source_type,
                    IncidentEvidence.source_id == IncidentIngestOutbox.source_id))
                .order_by(IncidentIngestOutbox.published_at)
                .limit(limit).with_for_update(skip_locked=True))
            result = await session.execute(
                update(IncidentIngestOutbox)
                .where(IncidentIngestOutbox.outbox_id.in_(stale.scalar_subquery()))
                .values(published_at=None))
            return int(result.rowcount or 0)


async def replay_dead_letter(redis_client, *, count: int = 50) -> int:
    """Operator-safe DLQ replay: validate, re-XADD to the main stream, delete from the DLQ only after
    the confirmed XADD. Entries that no longer parse as a valid envelope (e.g. truncated) stay in the
    DLQ for manual inspection. At-least-once: a crash between XADD and XDEL replays twice (idempotent)."""
    if redis_client is None:
        return 0
    replayed = 0
    for dlq_id, data in await redis_client.xrange(INGEST_DEAD_LETTER_KEY, min="-", max="+", count=count):
        try:
            norm = {(k.decode() if isinstance(k, bytes) else str(k)): (v.decode() if isinstance(v, bytes) else str(v))
                    for k, v in data.items()}
            fields = json.loads(norm["entry"])
            IngestEnvelope.from_stream_fields(fields)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("DLQ entry %s not replayable (%s); left in dead-letter", dlq_id, type(exc).__name__)
            continue
        if not await redis_client.xadd(INGEST_STREAM_KEY, fields):
            logger.error("DLQ replay XADD unconfirmed; entry %s kept", dlq_id)
            break
        await redis_client.xdel(INGEST_DEAD_LETTER_KEY, dlq_id)
        replayed += 1
    return replayed


async def dispatch_pending_safely(session_maker, redis_client, limit: int = DISPATCH_BATCH) -> int:
    """Never let dispatch fail the caller (source ingestion or consumer loop)."""
    try:
        return await dispatch_pending(session_maker, redis_client, limit)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Incident-ingest dispatch failed (%s); rows remain pending", type(exc).__name__)
        return 0
