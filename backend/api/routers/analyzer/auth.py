from fastapi import APIRouter, HTTPException, status
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
async def login(body: LoginRequest):
    exact_username = await verify_credentials(body.username, body.password)
    if not exact_username:
        logger.warning(f"Login rejected for unknown user '{body.username}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    role = await get_user_role(exact_username)
    token = create_access_token(exact_username, role=role)
    return LoginResponse(access_token=token)
