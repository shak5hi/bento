from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..security import DUMMY_HASH, current_user_id, hash_password, issue_token, rate_limit, verify_password
from ..state import state

router = APIRouter(prefix="/api/auth", tags=["auth"])
auth_limit = Depends(rate_limit("auth", limit=20, window_s=900))


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)


class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _user(row) -> dict:
    return {"id": str(row["id"]), "email": row["email"], "name": row["name"]}


@router.post("/register", status_code=201, dependencies=[auth_limit])
async def register(body: RegisterBody):
    row = await state.pg.fetchrow(
        """INSERT INTO users (email, name, password_hash) VALUES ($1, $2, $3)
           ON CONFLICT (email) DO NOTHING RETURNING id, email, name""",
        body.email.lower(),
        (body.name or "").strip() or None,
        hash_password(body.password),
    )
    if row is None:
        raise HTTPException(409, "An account with this email already exists")
    return {"token": issue_token(row["id"], row["email"]), "user": _user(row)}


@router.post("/login", dependencies=[auth_limit])
async def login(body: LoginBody):
    row = await state.pg.fetchrow("SELECT id, email, name, password_hash FROM users WHERE email = $1", body.email.lower())
    valid = verify_password(body.password, row["password_hash"] if row else DUMMY_HASH)
    if row is None or not valid:
        raise HTTPException(401, "Incorrect email or password")
    return {"token": issue_token(row["id"], row["email"]), "user": _user(row)}


@router.get("/me")
async def me(user_id: UUID = Depends(current_user_id)):
    row = await state.pg.fetchrow("SELECT id, email, name FROM users WHERE id = $1", user_id)
    if row is None:
        raise HTTPException(401, "Account no longer exists")
    return {"user": _user(row)}
