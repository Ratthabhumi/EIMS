from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.auth import create_access_token, verify_credentials

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    exact_username = verify_credentials(body.username, body.password)
    if not exact_username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    from app.core.auth import get_user_role
    role = get_user_role(exact_username)
    token = create_access_token(exact_username, role=role)
    return LoginResponse(access_token=token)
