from datetime import datetime, UTC
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Role(StrEnum):
    # StrEnum members ARE strings ("member" == Role.MEMBER), so they store
    # in a plain String column and serialize to JSON as-is.
    MEMBER = "member"
    EXEC = "exec"
    ADMIN = "admin"


# Higher number = more power. Kept as data (not if/elif chains) so "at least
# exec" is one comparison, and a new role is one line here plus a migration.
ROLE_RANK = {Role.MEMBER: 0, Role.EXEC: 1, Role.ADMIN: 2}


def has_role(user: "User", minimum: Role) -> bool:
    return ROLE_RANK[Role(user.role)] >= ROLE_RANK[minimum]


class Status(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"


class User(Base):
    __tablename__ = "users"
    # CHECK constraints: the database itself rejects any value outside these
    # lists, even from a typo in a script or a raw SQL UPDATE. The `name`
    # feeds the naming convention → "ck_users_role_valid".
    __table_args__ = (
        CheckConstraint(f"role IN ({', '.join(repr(r.value) for r in Role)})", name="role_valid"),
        CheckConstraint(f"status IN ({', '.join(repr(s.value) for s in Status)})", name="status_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True makes the DB itself reject a duplicate, even if two
    # registrations race past the app-level check. index=True because login
    # looks users up by email on every attempt.
    email: Mapped[str] = mapped_column(String(length=320), unique=True, index=True)
    # The bcrypt string ($2b$12$...), never the password itself.
    password_hash: Mapped[str] = mapped_column(String(length=60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # default= is what Python fills in on INSERT; server_default= is what the
    # DATABASE fills in, which is what existing rows get when a migration
    # adds the column. Keep the two the same.
    role: Mapped[str] = mapped_column(String(length=20), default=Role.MEMBER, server_default=Role.MEMBER.value)
    # New accounts can log in but do nothing until an exec approves them.
    status: Mapped[str] = mapped_column(String(length=20), default=Status.PENDING, server_default=Status.PENDING.value)


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(length=255))
    path: Mapped[str] = mapped_column(String(length=500), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Who uploaded it. Set from get_current_user, never from the request body.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
