"""Register + login routes.

THROWAWAY except for the last line of login: everything above
create_access_token() is the password proof step that Google OAuth replaces.
"""

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.passwords import DUMMY_HASH, MAX_PASSWORD_BYTES, hash_password, verify_password
from app.schemas import TokenOut, UserOut
from app.tokens import create_access_token

# A router is a mini-app: these routes get the /auth prefix and their own
# "auth" group in /docs, then main.py plugs the whole thing in.
router = APIRouter(prefix="/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


def normalize_email(email: str) -> str:
    # "Sean@Example.com " and "sean@example.com" are the same inbox, so they
    # must not become two accounts.
    return email.strip().lower()


@router.post("/register", response_model=UserOut, status_code=201)
def register(email: str = Form(), password: str = Form(), db: Session = Depends(get_db)):
    # Form() reads application/x-www-form-urlencoded or multipart fields —
    # what an HTML <form> sends — instead of a JSON body.
    email = normalize_email(email)
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(status_code=400, detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=400, detail=f"Password must be at most {MAX_PASSWORD_BYTES} bytes")

    # Saying "already registered" does reveal that the email has an account.
    # Unavoidable for a signup form without email verification (out of scope),
    # and harmless here — login is where we refuse to leak.
    if db.query(models.User).filter_by(email=email).first() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = models.User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Two requests for the same email can both pass the check above;
        # the unique constraint catches the loser here.
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    return user


# TODO: replace password login with Google OAuth (keep get_current_user)
@router.post("/login", response_model=TokenOut)
def login(email: str = Form(), password: str = Form(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=normalize_email(email)).first()

    # Always run bcrypt, even for an unknown email, so both failure paths
    # take the same time. A >72-byte password can't have been registered,
    # so it's simply wrong (and bcrypt 5 would raise on it).
    password_ok = len(password.encode()) <= MAX_PASSWORD_BYTES and verify_password(
        password, user.password_hash if user else DUMMY_HASH
    )
    if user is None or not password_ok:
        # Same message for both, so an attacker can't probe which emails exist.
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ↓ The seam. Everything above proves identity; this line is permanent.
    return TokenOut(access_token=create_access_token(user.id))
