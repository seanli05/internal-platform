from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True makes the DB itself reject a duplicate, even if two
    # registrations race past the app-level check. index=True because login
    # looks users up by email on every attempt.
    email: Mapped[str] = mapped_column(String(length=320), unique=True, index=True)
    # The bcrypt string ($2b$12$...), never the password itself.
    password_hash: Mapped[str] = mapped_column(String(length=60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Photo(Base):
    __tablename__ = "photos"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(length=255))
    path: Mapped[str] = mapped_column(String(length=500), unique=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    # Who uploaded it. Set from get_current_user, never from the request body.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
