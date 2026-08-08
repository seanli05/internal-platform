"""Alembic environment.

The database URL comes from the app's settings (i.e. the environment), never from
alembic.ini, so migrations and the app can never disagree about which DB they mean.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models yet (Phase 0). Later phases point this at the shared metadata so
# `alembic revision --autogenerate` works.
target_metadata = None


def get_url() -> str:
    """Return the SQLAlchemy URL for migrations (sync driver: psycopg 3)."""
    return str(get_settings().database_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = create_engine(get_url(), pool_pre_ping=True)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
