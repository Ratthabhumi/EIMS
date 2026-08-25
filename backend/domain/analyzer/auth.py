from sqlalchemy.future import select
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.getenv("JWT_SECRET", "eventiq-dev-secret-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

USERS = {
    "admin": {"password": "P@ssw0rd", "role": "admin"},
    "TAR": {"password": "T@ssw0rd", "role": "user"},
    "Mew": {"password": "M@ssw0rd", "role": "user"},
}

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "P@ssw0rd")
USERS["admin"]["password"] = ADMIN_PASSWORD

security = HTTPBearer(auto_error=False)

def create_access_token(username: str, role: str = "user") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

from backend.infrastructure.database import get_db_session
from backend.domain.analyzer.models.user import User

async def verify_credentials(username: str, password: str) -> str | None:
    async for db in get_db_session():
        try:
            user = (await db.execute(select(User).filter(User.username == username))).scalars().first()
            if user and user.password == password:
                return user.username
            
            for exact_username, user_info in USERS.items():
                if exact_username.lower() == username.lower():
                    if user_info["password"] == password:
                        if not (await db.execute(select(User).filter(User.username == exact_username))).scalars().first():
                            db.add(User(username=exact_username, password=user_info["password"], role=user_info["role"]))
                            await db.commit()
                        return exact_username
                    break
            return None
        except Exception as e:
            print(f"Auth error: {e}")
            return None

async def get_user_role(username: str) -> str:
    async for db in get_db_session():
        try:
            user = (await db.execute(select(User).filter(User.username == username))).scalars().first()
            if user:
                return user.role
            return USERS.get(username, {}).get("role", "user")
        except Exception:
            return "user"

async def seed_users():
    async for db in get_db_session():
        try:
            for username, user_info in USERS.items():
                if not (await db.execute(select(User).filter(User.username == username))).scalars().first():
                    db.add(User(username=username, password=user_info["password"], role=user_info["role"]))
            await db.commit()
        except Exception as e:
            print(f"Failed to seed users: {e}")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if not credentials:
        return "guest"
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            return "guest"
        return username
    except Exception:
        return "guest"
