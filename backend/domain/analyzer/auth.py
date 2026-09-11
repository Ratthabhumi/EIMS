from sqlalchemy.future import select
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.config import settings
from backend.core.logger import get_logger

logger = get_logger("eims.analyzer.auth")

# Security & Cryptographic Auth Contracts (Core Law 5) - env-driven via EIMSSettings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRES_MINUTES

# Auth Mode: "demo" = no login required; "secure" = auth enforced
AUTH_MODE = settings.AUTH_MODE.lower()

# Legacy in-memory demo accounts have been removed. Credentials are verified
# exclusively against the hashed `users` table seeded at startup.
USER_ALREADY_SEEDED = False

security = HTTPBearer(auto_error=False)


# -------------------------------------------------------------------------
# Password Hashing & Verification (PBKDF2-SHA256, salted, migration-aware)
# -------------------------------------------------------------------------
_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Derives a salted PBKDF2-SHA256 hash: pbkdf2_sha256$<iter>$<salt_hex>$<hash_hex>."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_pbkdf2(password: str, iterations: int, salt_hex: str, expected_hex: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iterations)
    return secrets.compare_digest(digest.hex(), expected_hex)


def verify_password(password: str, stored: str) -> bool:
    """Verifies a password against a stored credential, tolerating legacy plaintext rows."""
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2_sha256":
        return _verify_pbkdf2(password, int(parts[1]), parts[2], parts[3])
    # Legacy plaintext stored credential (pre-hardening rows)
    return secrets.compare_digest(stored, password)


def _resolve_admin_password() -> str:
    """Returns the seeded admin password: explicit EIMS_ADMIN_PASSWORD or a generated one in dev."""
    password = settings.ADMIN_PASSWORD or os.getenv("ADMIN_PASSWORD")
    if password:
        return password
    if settings.ENVIRONMENT.lower() == "development":
        generated = secrets.token_urlsafe(18)
        logger.warning(
            f"[DEV-ONLY] No EIMS_ADMIN_PASSWORD configured. Generated one-time admin password: {generated}"
        )
        return generated
    raise RuntimeError("EIMS_ADMIN_PASSWORD must be set outside the development tier.")


def create_access_token(username: str, role: str = "user") -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


from backend.infrastructure.database import get_db_session
from backend.domain.analyzer.models.user import User


def _normalize_case(username: str) -> str:
    """Preserves the authoritative username casing from the seeded admin account."""
    return "admin" if username.lower() == "admin" else username


async def verify_credentials(username: str, password: str) -> str | None:
    """Validates credentials against the hashed users table (auto-upgrades legacy plaintext rows)."""
    async for db in get_db_session():
        try:
            user = (await db.execute(select(User).filter(User.username == _normalize_case(username)))).scalars().first()
            if user and verify_password(password, user.password or ""):
                if not user.password.startswith("pbkdf2_sha256"):
                    user.password = hash_password(password)
                    await db.commit()
                return user.username
            return None
        except Exception as e:
            logger.error(f"Auth verification error: {e}")
            return None


async def get_user_role(username: str) -> str:
    """Returns the stored role for a username, defaulting to the safe 'user' role."""
    async for db in get_db_session():
        try:
            user = (await db.execute(select(User).filter(User.username == _normalize_case(username)))).scalars().first()
            if user:
                return user.role or "user"
            return "user"
        except Exception:
            return "user"


async def seed_users():
    """Creates the hashed admin bootstrap account once; idempotent across restarts."""
    global USER_ALREADY_SEEDED
    if USER_ALREADY_SEEDED:
        return
    async for db in get_db_session():
        try:
            existing = (await db.execute(select(User).filter(User.username == "admin"))).scalars().first()
            if not existing:
                admin_password = _resolve_admin_password()
                db.add(User(username="admin", password=hash_password(admin_password), role="admin"))
                await db.commit()
                logger.info("Admin bootstrap account seeded with hashed credential.")
            USER_ALREADY_SEEDED = True
        except Exception as e:
            logger.error(f"Failed to seed admin user: {e}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Resolves the authenticated username from a bearer JWT.

    In DEMO mode: returns "demo" identity when no token provided (no login required).
    In SECURE mode: requires valid JWT, raises 401 if missing/invalid.
    """
    # Demo mode: allow unauthenticated access with a special identity
    if settings.AUTH_MODE.lower() == "demo":
        if not credentials or not credentials.credentials:
            return "demo"
        try:
            payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            return username if username is not None else "demo"
        except Exception:
            return "demo"

    # Secure mode: require valid authentication
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if secrets.compare_digest(credentials.credentials, settings.ADMIN_TOKEN):
        return "admin"
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def require_admin(username: str = Depends(get_current_user)) -> str:
    """Requires an authenticated admin user (JWT with role='admin'); otherwise 403."""
    # Demo identity cannot be admin
    if username in ("guest", "demo"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    role = await get_user_role(username)
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return username


async def verify_admin_token(
    authorization: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Requires the configured admin bearer token (env: EIMS_ADMIN_TOKEN); otherwise 401."""
    if not authorization or not authorization.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    if not secrets.compare_digest(authorization.credentials, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return authorization.credentials


async def require_admin_or_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """Admin-scoped gate accepting either a valid admin JWT or the configured admin bearer token.

    In DEMO mode: returns 'demo' if unauthenticated, allowing demo write operations.
    In SECURE mode: requires either an admin JWT (role='admin') or configured ADMIN_TOKEN.
    """
    if not credentials or not credentials.credentials:
        if settings.AUTH_MODE.lower() == "demo":
            return "demo"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    raw_token = credentials.credentials
    # 1. Validate static ADMIN_TOKEN
    if secrets.compare_digest(raw_token, settings.ADMIN_TOKEN):
        return "admin"

    # 2. Validate JWT with admin role
    try:
        payload = jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if role != "admin":
            db_role = await get_user_role(username)
            if db_role != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")