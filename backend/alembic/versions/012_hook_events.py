"""hook events table and audit events session index

Revision ID: 012
Revises: 011
Create Date: 2026-04-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hook_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hook_type", sa.String(), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_hook_events_agent_session_id",
        "hook_events",
        ["agent_session_id"],
    )

    # Expression index on audit_events JSONB for session lookups
    op.create_index(
        "ix_audit_events_session_id",
        "audit_events",
        [sa.text("(metadata ->> 'session_id')")],
        postgresql_where=sa.text("metadata ->> 'session_id' IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_session_id", table_name="audit_events")
    op.drop_index("ix_hook_events_agent_session_id", table_name="hook_events")
    op.drop_table("hook_events")
