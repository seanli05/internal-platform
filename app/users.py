"""User management: who am I, the approval queue, and role changes.

PERMANENT. Unlike auth.py, nothing here cares how a user logged in.
"""

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.models import Role, Status
from app.permissions import require_role
from app.schemas import UserOut
from app.tokens import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: models.User = Depends(get_current_user)):
    # Deliberately get_current_user, NOT require_role: a pending user must be
    # able to reach this, so the frontend can show "awaiting approval".
    # (Lives here rather than auth.py because auth.py gets replaced by OAuth.)
    return user


@router.get("", response_model=list[UserOut])
def list_users(
    status: Status | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role(Role.EXEC)),
):
    # `status: Status | None = None` is a query parameter: GET /users?status=pending.
    # Typing it as the enum means FastAPI answers 422 for ?status=banana.
    # The `_` name says "this dependency is here for its check, not its value".
    query = db.query(models.User)
    if status is not None:
        query = query.filter_by(status=status)
    return query.order_by(models.User.created_at).all()


def get_user_or_404(user_id: int, db: Session) -> models.User:
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/approve", response_model=UserOut)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role(Role.EXEC)),
):
    user = get_user_or_404(user_id, db)
    # Approving someone already approved is a harmless no-op, not an error.
    user.status = Status.APPROVED
    db.commit()
    return user


@router.post("/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int,
    role: Role = Form(),
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_role(Role.ADMIN)),
):
    # An admin demoting themselves could leave the app with zero admins and no
    # way to make one except the CLI script. Another admin has to do it.
    if user_id == admin.id:
        raise HTTPException(status_code=403, detail="You can't change your own role")
    user = get_user_or_404(user_id, db)
    user.role = role
    db.commit()
    return user
