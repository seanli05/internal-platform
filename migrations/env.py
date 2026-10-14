"""Alembic's entry point: every alembic command runs this file.

Its whole job is to hand Alembic two things:
  1. a connection to the real database        (what the schema IS)
  2. Base.metadata from our models            (what the schema SHOULD BE)
Autogenerate diffs those two; upgrade/downgrade run scripts over (1).
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Importing models registers User and Photo on Base.metadata. Without this
# import the metadata is empty, and autogenerate would think you deleted
# every table and helpfully write a migration dropping them all.
import app.models  # noqa: F401
from app.db import DATABASE_URL, Base

config = context.config

# Sets up the logging that prints "Running upgrade -> a1b2c3" etc.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# One source of truth for the URL: app/db.py. alembic.ini deliberately has
# none, so moving to Postgres stays a one-line change in db.py.
# `-x db_url=...` overrides it for a single command — e.g. to try a migration
# against a scratch copy before touching photos.db:
#   alembic -x db_url=sqlite:///./scratch.db upgrade head
url = context.get_x_argument(as_dictionary=True).get("db_url", DATABASE_URL)

# Both modes pass the same options, so define them once.
configure_opts = dict(
    target_metadata=target_metadata,
    # SQLite's ALTER TABLE can't drop or alter columns/constraints. Batch
    # mode works around it: create the new table, copy rows, drop the old,
    # rename. On Postgres the same batch ops become plain ALTERs, so the
    # migration scripts work on both.
    render_as_batch=True,
    # Also diff column TYPES (e.g. String(20) -> String(50)), not just
    # added/removed columns.
    compare_type=True,
)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it.

    Handy for reading exactly what a migration will do to the database.
    """
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"}, **configure_opts)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """The normal path: connect and run the migrations for real."""
    # NullPool: a CLI command opens one connection and exits; no pool needed.
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **configure_opts)
        # Each migration run is one transaction: on SQLite and Postgres a
        # failure partway through rolls the whole thing back.
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
