"""Explicit operator maintenance; no scheduler and no AnalysisHistory access."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, or_, select

from backend.domain.analyzer.models.session import AnalyzerSession, LoginWindow
from backend.domain.analyzer.services.session_security import WINDOW_SECONDS
from backend.infrastructure.db_identity import require_destructive_target


async def cleanup_auth_records(db, *, retention_seconds: int, batch_size: int = 100,
                               now=None, dry_run: bool = True):
    """One bounded transaction. Caller supplies institution-approved retention.

    Dry-run is the default: a library call with no arguments must never delete.
    A destructive run must additionally prove the live connection is the intended
    target (``require_destructive_target`` on the same transaction), so a caller
    cannot turn a dry-run tool into a destructive one by omitting a flag.

    Use a fresh AsyncSession. PostgreSQL locks skip rows another worker owns;
    login's atomic upsert waits for deletion, then creates a fresh expired window.
    Never removes an unrevoked/unexpired session or a live throttle window.
    Any exception rolls back both tables. Return counts only, never identifiers.
    """
    if retention_seconds < WINDOW_SECONDS or not 1 <= batch_size <= 1000:
        raise ValueError('Require retention >= login window and batch size 1..1000')
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=retention_seconds)
    counts = {}
    async with db.begin():
        if not dry_run:
            # Same transaction and connection as the DELETE below.
            await require_destructive_target(db, operation="session_cleanup")
        for model, eligible in [
            (AnalyzerSession, or_(AnalyzerSession.expires_at < cutoff,
                                 AnalyzerSession.revoked_at < cutoff)),
            (LoginWindow, LoginWindow.started_at < cutoff),
        ]:
            keys = (await db.execute(select(model.id).where(eligible).order_by(model.id)
                                    .limit(batch_size).with_for_update(skip_locked=True))).scalars().all()
            if keys and not dry_run:
                await db.execute(delete(model).where(model.id.in_(keys)))
            counts[model.__tablename__] = len(keys)
    return counts
