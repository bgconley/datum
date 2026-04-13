"""evaluation tables

Revision ID: 005
Revises: 004
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("queries", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "evaluation_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("evaluation_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("retrieval_config_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id")),
        sa.Column("embedding_model", sa.String()),
        sa.Column("embedding_model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("reranker_model", sa.String()),
        sa.Column("reranker_model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("version_scope", sa.String(), nullable=False, server_default="current"),
        sa.Column("chunking_config", JSONB),
        sa.Column("fusion_weights", JSONB),
        sa.Column("search_overrides", JSONB),
        sa.Column("results", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_sets")
