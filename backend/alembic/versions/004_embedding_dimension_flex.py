"""enforce embedding dimension contract

Revision ID: 004
Revises: 003
Create Date: 2026-04-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep dimensions explicit for ParadeDB/pgvector HNSW index compatibility.
    op.execute(
        """
        ALTER TABLE chunk_embeddings
        ADD CONSTRAINT chunk_embeddings_dimensions_1024_ck
        CHECK (dimensions = 1024)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE chunk_embeddings
        DROP CONSTRAINT IF EXISTS chunk_embeddings_dimensions_1024_ck
        """
    )
