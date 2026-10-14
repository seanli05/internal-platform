"""The token step: issue and verify signed access tokens.

PERMANENT. Whatever proves identity (a password today, Google tomorrow) ends
by calling create_access_token(user.id). Every protected route depends on
get_current_user. Neither function knows or cares how the user logged in.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.config import SECRET_KEY
from app.db import get_db

ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(hours=12)

# Reads "Authorization: Bearer <token>" and hands back the parts. It also
# adds the "Authorize" button to /docs. auto_error=False means a missing
# header gives you None instead of FastAPI raising its own error, so YOUR
# code decides what a failure looks like.
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        # "sub" (subject) is a registered JWT claim: who this token is about.
        # The spec says it's a string, and PyJWT enforces that on decode.
        "sub": str(user_id),
        # "exp" is checked automatically by jwt.decode. PyJWT turns the
        # datetime into a Unix timestamp.
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    headers = {"WWW-Authenticate": "Bearer"}

    if credentials is None:
        raise HTTPException(401, "Not authenticated", headers=headers)

    # Only token parsing lives in the try, so it's clear which errors are
    # expected here and nothing else gets swallowed.
    try:
        # require: a token missing exp or sub is rejected as invalid
        # (MissingRequiredClaimError) instead of crashing on a KeyError later.
        decoded_payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        user_id = int(decoded_payload["sub"])
    except jwt.ExpiredSignatureError:
        # Must come before InvalidTokenError, which is its parent class.
        raise HTTPException(401, "Token expired", headers=headers) from None
    except (jwt.InvalidTokenError, ValueError):
        # ValueError: sub was signed by us but isn't a number.
        raise HTTPException(401, "Invalid token", headers=headers) from None

    # The signature proves we issued this token; it doesn't prove the user
    # still exists.
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(401, "User not found", headers=headers)
    return user
