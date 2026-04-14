"""phase 7 intelligence graph tables

Revision ID: 008
Revises: 007
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "target_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="SET NULL"),
        ),
        sa.Column("link_type", sa.String(), nullable=False),
        sa.Column("anchor_text", sa.Text()),
        sa.Column("auto_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "document_links_source_version_idx",
        "document_links",
        ["source_version_id"],
    )
    op.create_index(
        "document_links_target_document_idx",
        "document_links",
        ["target_document_id"],
    )

    op.create_table(
        "entity_relationships",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column(
            "evidence_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "evidence_chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
        ),
        sa.Column("evidence_text", sa.Text()),
        sa.Column("evidence_start_char", sa.Integer()),
        sa.Column("evidence_end_char", sa.Integer()),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "entity_relationships_source_entity_idx",
        "entity_relationships",
        ["source_entity_id"],
    )
    op.create_index(
        "entity_relationships_target_entity_idx",
        "entity_relationships",
        ["target_entity_id"],
    )
    op.create_index(
        "entity_relationships_evidence_version_idx",
        "entity_relationships",
        ["evidence_version_id"],
    )

    op.create_table(
        "insights",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("insight_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("evidence", JSONB),
        sa.Column("created_by_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("insights_project_status_idx", "insights", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("insights_project_status_idx", table_name="insights")
    op.drop_table("insights")
    op.drop_index(
        "entity_relationships_evidence_version_idx",
        table_name="entity_relationships",
    )
    op.drop_index(
        "entity_relationships_target_entity_idx",
        table_name="entity_relationships",
    )
    op.drop_index(
        "entity_relationships_source_entity_idx",
        table_name="entity_relationships",
    )
    op.drop_table("entity_relationships")
    op.drop_index("document_links_target_document_idx", table_name="document_links")
    op.drop_index("document_links_source_version_idx", table_name="document_links")
    op.drop_table("document_links")
