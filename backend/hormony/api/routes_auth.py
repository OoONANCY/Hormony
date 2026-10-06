from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..auth import (FAILED_LOGINS, TOKEN_EXPIRE_HOURS, create_access_token, get_current_user, hash_password,
                    verify_password)
from ..db import get_db
from ..models import Profile, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password("no account has this password")


def _session(user: User) -> dict:
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "expires_in": TOKEN_EXPIRE_HOURS * 3600,
            "user_id": user.id, "email": user.email}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="That email already has an account. Sign in instead.")
    first = db.query(User.id).first() is None
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    if first:  # records made before this server had accounts belong to whoever sets the first account up
        db.query(Profile).filter(Profile.kind == "personal", Profile.owner_id.is_(None)).update(
            {Profile.owner_id: user.id}, synchronize_session=False)
    db.commit()
    db.refresh(user)
    return _session(user)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    key = (email, request.client.host if request.client else "")
    wait = FAILED_LOGINS.retry_after(key)
    if wait:
        raise HTTPException(429, f"Too many wrong passwords. Try again in {max(1, round(wait / 60))} min.",
                            headers={"Retry-After": str(wait)})
    user = db.query(User).filter(User.email == email).first()
    ok = verify_password(body.password, user.password_hash if user else _dummy_hash())  # same work either way,
    if not user or not ok:                                                                 # so timing doesn't reveal accounts
        FAILED_LOGINS.fail(key)
        raise HTTPException(status_code=401, detail="Wrong email or password")
    FAILED_LOGINS.clear(key)
    return _session(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email}
