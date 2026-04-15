"""add canonical path to version head events

Revision ID: 011
Revises: 010
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("version_head_events", sa.Column("canonical_path", sa.String(), nullable=True))
    op.execute(
        """
        UPDATE version_head_events AS vhe
        SET canonical_path = d.canonical_path
        FROM documents AS d
        WHERE d.id = vhe.document_id
        """
    )
    op.alter_column("version_head_events", "canonical_path", nullable=False)
    op.create_index(
        "version_head_events_doc_branch_path_idx",
        "version_head_events",
        ["document_id", "branch", "canonical_path"],
    )


def downgrade() -> None:
    op.drop_index("version_head_events_doc_branch_path_idx", table_name="version_head_events")
    op.drop_column("version_head_events", "canonical_path")
