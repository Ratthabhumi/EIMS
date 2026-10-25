from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from datetime import datetime, timezone
import secrets
import jwt
from sqlalchemy import select
from backend.domain.analyzer import auth as auth_core
from backend.domain.analyzer.models.user import User
from backend.domain.analyzer.models.session import AnalyzerSession
from backend.domain.analyzer.services.session_security import digest, reserve_login, revoke_session
from sqlalchemy.ext.asyncio import AsyncSession
from backend.infrastructure.database import get_db_session
from backend.domain.analyzer.auth import get_current_user
from backend.core.config import settings
from pydantic import BaseModel, Field

from backend.core.logger import get_logger
from backend.domain.analyzer.auth import create_access_token, get_user_role, verify_credentials

logger = get_logger("eims.api.auth")

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db_session)):
    await reserve_login(db, body.username, request.client.host if request.client else 'unknown')
    exact_username = await verify_credentials(body.username, body.password, db)
    if not exact_username:
        logger.warning("Login rejected.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    role = await get_user_role(exact_username, db)
    account = (await db.execute(select(User).where(User.username == exact_username))).scalars().one()
    sid = secrets.token_urlsafe(32)
    token = create_access_token(exact_username, role=role, session_id=sid)
    payload = jwt.decode(token, auth_core.SECRET_KEY, algorithms=[auth_core.ALGORITHM])
    now = datetime.now(timezone.utc)
    db.add(AnalyzerSession(id=digest(sid), user_id=account.id, username=account.username,
        credential_version=digest(account.password or ''), created_at=now, last_seen=now,
        expires_at=datetime.fromtimestamp(payload['exp'], timezone.utc)))
    await db.commit()
    return LoginResponse(access_token=token)


@router.get('/session')
async def session_info(user: str = Depends(get_current_user)):
    return {'username': user, 'mode': settings.AUTH_MODE.lower()}


@router.post('/logout')
async def logout(user: str = Depends(get_current_user),
                 credentials: HTTPAuthorizationCredentials = Depends(auth_core.security),
                 db: AsyncSession = Depends(get_db_session)):
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, auth_core.SECRET_KEY, algorithms=[auth_core.ALGORITHM])
            if isinstance(payload.get('sid'), str):
                await revoke_session(db, payload['sid'], user)
        except jwt.PyJWTError:
            pass
    return {'authenticated':False}
