"""Small PostgreSQL-backed session lifecycle and fixed-window login throttle."""
import hashlib
from datetime import datetime, timedelta, timezone
from sqlalchemy import case, func, update
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from backend.domain.analyzer.models.session import AnalyzerSession, LoginWindow

IDLE_SECONDS = 900
WINDOW_SECONDS = 60
ACCOUNT_LIMIT = 8
CLIENT_LIMIT = 120
THROTTLE_NAMESPACE = 'auth-v1'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def reserve_login(db, username, peer):
    now = datetime.now(timezone.utc)
    # Peer reservation first: blocked clients cannot create unlimited account keys.
    for scope, maximum in [(f'peer:{peer}', CLIENT_LIMIT), (f'account:{username.strip().casefold()}', ACCOUNT_LIMIT)]:
        key = digest(THROTTLE_NAMESPACE + ':' + scope)
        expired = LoginWindow.started_at <= now - timedelta(seconds=WINDOW_SECONDS)
        stmt = insert(LoginWindow).values(id=key, attempts=1, started_at=now).on_conflict_do_update(
            index_elements=[LoginWindow.id], set_={
                'attempts':case((expired, 1), else_=func.least(LoginWindow.attempts + 1, maximum + 1)),
                'started_at':case((expired, now), else_=LoginWindow.started_at),
            }).returning(LoginWindow.attempts, LoginWindow.started_at)
        count, started = (await db.execute(stmt)).one()
        await db.commit()
        if count > maximum:
            retry = max(1, int((started + timedelta(seconds=WINDOW_SECONDS) - now).total_seconds()) + 1)
            raise HTTPException(429, detail='Too many login attempts; retry later', headers={'Retry-After':str(retry)})


async def validate_session(db, sid, user, touch=True):
    now = datetime.now(timezone.utc)
    stmt = update(AnalyzerSession).where(
        AnalyzerSession.id == digest(sid), AnalyzerSession.user_id == user.id,
        AnalyzerSession.username == user.username, AnalyzerSession.revoked_at.is_(None),
        AnalyzerSession.credential_version == digest(user.password or ''),
        AnalyzerSession.expires_at > now,
        AnalyzerSession.last_seen > now - timedelta(seconds=IDLE_SECONDS),
    ).values(last_seen=now if touch else AnalyzerSession.last_seen).returning(AnalyzerSession.id)
    valid = (await db.execute(stmt)).scalar_one_or_none()
    await db.commit()
    if valid is None:
        raise HTTPException(401, detail='Invalid token')


async def revoke_session(db, sid, username):
    await db.execute(update(AnalyzerSession).where(
        AnalyzerSession.id == digest(sid), AnalyzerSession.username == username,
    ).values(revoked_at=datetime.now(timezone.utc)))
    await db.commit()
