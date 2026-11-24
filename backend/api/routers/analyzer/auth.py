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
    # Product rule: EIMS has no application login. Engineers use the Portal without
    # a username/password. Keep the route only so old clients receive an explicit
    # Gone response instead of a silent auth bypass.
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Application login is not used. EIMS Portal access does not require a user session.",
    )


@router.get('/session')
async def session_info(
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    account = (await db.execute(select(User).where(User.username == user))).scalars().first()
    is_admin = bool(account and account.role == 'admin')
    return {
        'username': user,
        'mode': 'open_access',
        'application_login': False,
        'capabilities': {'knowledge_review': bool(is_admin or (account and account.knowledge_reviewer))},
    }


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
