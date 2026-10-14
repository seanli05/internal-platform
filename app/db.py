"""Database wiring: one engine, one session factory, one declarative base.

This file is written out in full as your reference for style/idiom.
models.py, schemas.py and main.py are yours to write.
"""

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# A SQLite file next to the repo root. Swapping this string for a
# "postgresql+psycopg://..." URL later is the *only* line that has to change.
DATABASE_URL = "sqlite:///./photos.db"

# The engine owns the connection pool. Create exactly ONE per process.
# check_same_thread=False: SQLite normally refuses to let a connection cross
# threads, and FastAPI runs sync endpoints in a threadpool. Safe here because
# SQLAlchemy hands each session its own connection.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# A factory, not a session. Call SessionLocal() to get a fresh unit of work.
# autoflush=False keeps SQLAlchemy from sneaking INSERTs out before you commit.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every model subclasses this. Base.metadata collects the table defs."""

    # Give every constraint and index a predictable name. Unnamed ones
    # (SQLite's default) can't be dropped or altered by a migration, because
    # the migration has to say WHICH constraint. e.g. the unique email
    # constraint becomes "uq_users_email", photos' FK "fk_photos_user_id_users".
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed.

    The yield splits this into setup / teardown. FastAPI runs everything
    before the yield, injects the session into your endpoint, then runs the
    finally block once the response is sent — even if the endpoint raised.

    .next() used to grab a new session for every endpoint request
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
