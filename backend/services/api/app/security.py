import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from bento_core.config import require, settings

from .state import state

JWT_SECRET = require("JWT_SECRET")
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=11)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# Compared against when the email is unknown, so both paths take the same time.
DUMMY_HASH = hash_password("timing-safe-placeholder")


def issue_token(user_id: UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": email, "iat": now, "exp": now + timedelta(hours=settings.jwt_ttl_hours)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


async def current_user_id(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> UUID:
    if creds is None:
        raise HTTPException(401, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
        return UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token") from None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(bucket: str, limit: int, window_s: int):
    """Fixed-window limiter in Redis, shared across gateway replicas."""

    async def dependency(request: Request) -> None:
        window = int(time.time() // window_s)
        key = f"ratelimit:{bucket}:{client_ip(request)}:{window}"
        count = await state.redis.incr(key)
        if count == 1:
            await state.redis.expire(key, window_s)
        if count > limit:
            raise HTTPException(429, "Too many requests, slow down", headers={"Retry-After": str(window_s)})

    return dependency
