"""Authentication routes + the current-user dependency."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import User
from .security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterReq(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginReq(BaseModel):
    username_or_email: str
    password: str


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    payload = decode_token(authorization.split(" ", 1)[1])
    if not payload:
        raise HTTPException(401, "invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "user not found")
    return user


def _public(user: User) -> dict:
    return {"id": user.id, "username": user.username, "email": user.email,
            "is_admin": user.is_admin}


@router.post("/register")
def register(req: RegisterReq, db: Session = Depends(get_db)):
    exists = db.query(User).filter(
        (User.username == req.username) | (User.email == req.email)
    ).first()
    if exists:
        raise HTTPException(409, "username or email already taken")
    user = User(
        username=req.username, email=req.email,
        hashed_password=hash_password(req.password), is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_token(user.id, user.username, user.is_admin)
    return {"token": token, "user": _public(user)}


@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == req.username_or_email) | (User.email == req.username_or_email)
    ).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(401, "invalid credentials")
    token = create_token(user.id, user.username, user.is_admin)
    return {"token": token, "user": _public(user)}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"user": _public(user)}
