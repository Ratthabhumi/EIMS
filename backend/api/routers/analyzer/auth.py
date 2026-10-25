from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.infrastructure.database import get_db_session
from backend.domain.analyzer.auth import get_current_user
from backend.core.config import settings
from pydantic import BaseModel

from backend.core.logger import get_logger
from backend.domain.analyzer.auth import create_access_token, get_user_role, verify_credentials

logger = get_logger("eims.api.auth")

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db_session)):
    exact_username = await verify_credentials(body.username, body.password, db)
    if not exact_username:
        logger.warning("Login rejected.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    role = await get_user_role(exact_username, db)
    token = create_access_token(exact_username, role=role)
    return LoginResponse(access_token=token)


@router.get('/session')
async def session_info(user: str = Depends(get_current_user)):
    return {'username': user, 'mode': settings.AUTH_MODE.lower()}
