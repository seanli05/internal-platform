"""Enable the pgvector extension.

Baseline migration. No tables yet — this only makes the `vector` type available,
which every later phase (CLIP embeddings, face embeddings) depends on.

Revision ID: 0001_enable_pgvector
Revises:
Create Date: 2026-07-28

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
