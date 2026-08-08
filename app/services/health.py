"""Health checks."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def check_database(session: AsyncSession) -> None:
    """Verify the database is reachable.

    Raises `sqlalchemy.exc.SQLAlchemyError` if the round-trip fails; the caller
    turns that into a 503 rather than swallowing it.
    """
    await session.execute(text("SELECT 1"))
