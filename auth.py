"""
Authentication utilities: password hashing, JWT creation/verification,
and FastAPI dependencies for getting the current logged-in user via
an httpOnly cookie ("access_token").
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from database import get_db_connection

from models import UserInDB

SECRET_KEY = os.getenv("SECRET_KEY", "insecure_dev_secret_change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 hours

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# blacklisted tokens (e.g. after logout)
blacklisted_tokens: set = set()

# ---------------------------------------------------------------------
# In-memory "database". Restarting the server clears all data - this is
# intentional for a demo/starter project. Swap this out for a real DB
# (SQLite/Postgres) for production use.
# ---------------------------------------------------------------------


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user(username: str) -> Optional[UserInDB]:
    conn = get_db_connection()

    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return UserInDB(
        username=row["username"],
        email=row["email"],
        full_name=row["full_name"],
        hashed_password=row["hashed_password"],
        disabled=bool(row["disabled"])
    )


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_token_from_request(request: Request) -> Optional[str]:
    """Read the JWT from the access_token cookie, or the Authorization header."""
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1]
    return None


async def get_current_user(request: Request) -> Optional[UserInDB]:
    """Returns the current user, or None if not authenticated (does not raise)."""
    token = await get_token_from_request(request)
    if not token or token in blacklisted_tokens:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    return get_user(username)


async def get_current_active_user(request: Request) -> UserInDB:
    """Dependency that requires a logged-in, non-disabled user (raises 401 otherwise)."""
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
