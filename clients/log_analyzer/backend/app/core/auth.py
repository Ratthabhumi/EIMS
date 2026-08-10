import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.getenv("JWT_SECRET", "eventiq-dev-secret-change-in-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Defined Users
USERS = {
    "admin": {"password": "P@ssw0rd", "role": "admin"},
    "TAR": {"password": "T@ssw0rd", "role": "user"},
    "Mew": {"password": "M@ssw0rd", "role": "user"},
}

# In production, use os.getenv overrides for admin if needed
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "P@ssw0rd")
USERS["admin"]["password"] = ADMIN_PASSWORD

security = HTTPBearer()


def create_access_token(username: str, role: str = "user") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


from app.core.database import SessionLocal
from app.models.user import User

def verify_credentials(username: str, password: str) -> str | None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.password == password:
            return user.username
        
        # Fallback to hardcoded admin/users if DB is empty or user not found
        for exact_username, user_info in USERS.items():
            if exact_username.lower() == username.lower():
                if user_info["password"] == password:
                    # Seed to DB automatically
                    if not db.query(User).filter(User.username == exact_username).first():
                        db.add(User(username=exact_username, password=user_info["password"], role=user_info["role"]))
                        db.commit()
                    return exact_username
                break
        return None
    finally:
        db.close()

def get_user_role(username: str) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user.role
        return USERS.get(username, {}).get("role", "user")
    finally:
        db.close()

def seed_users():
    db = SessionLocal()
    try:
        for username, user_info in USERS.items():
            if not db.query(User).filter(User.username == username).first():
                db.add(User(username=username, password=user_info["password"], role=user_info["role"]))
        db.commit()
    except Exception as e:
        print(f"Failed to seed users: {e}")
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
