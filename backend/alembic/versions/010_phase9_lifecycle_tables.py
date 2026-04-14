"""phase 9 lifecycle tables

Revision ID: 010
Revises: 009
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column("client_type", sa.String(), nullable=False, server_default=sa.text("'generic'")),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "enforcement_mode",
            sa.String(),
            nullable=False,
            server_default=sa.text("'advisory'"),
        ),
        sa.Column("is_dirty", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dirty_reasons", JSONB),
        sa.Column("last_preflight_at", sa.DateTime(timezone=True)),
        sa.Column("last_preflight_action", sa.String()),
        sa.Column("last_flush_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("agent_sessions_session_id_idx", "agent_sessions", ["session_id"])
    op.create_index("agent_sessions_project_status_idx", "agent_sessions", ["project_id", "status"])

    op.create_table(
        "session_deltas",
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
        sa.Column("delta_type", sa.String(), nullable=False),
        sa.Column("detail", JSONB, nullable=False),
        sa.Column("summary_text", sa.Text()),
        sa.Column("flushed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "session_deltas_session_flush_idx",
        "session_deltas",
        ["agent_session_id", "flushed", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("session_deltas_session_flush_idx", table_name="session_deltas")
    op.drop_table("session_deltas")
    op.drop_index("agent_sessions_project_status_idx", table_name="agent_sessions")
    op.drop_index("agent_sessions_session_id_idx", table_name="agent_sessions")
    op.drop_table("agent_sessions")
