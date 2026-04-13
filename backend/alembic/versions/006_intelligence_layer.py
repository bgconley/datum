"""intelligence layer tables

Revision ID: 006
Revises: 005
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("metadata", JSONB),
        sa.Column("first_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("entity_type", "canonical_name"),
    )

    op.create_table(
        "entity_mentions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_id", UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("document_chunks.id", ondelete="CASCADE")),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("text_start_char", sa.Integer(), nullable=False),
        sa.Column("text_end_char", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("entity_mentions_entity_id_idx", "entity_mentions", ["entity_id"])
    op.create_index("entity_mentions_chunk_id_idx", "entity_mentions", ["chunk_id"])
    op.create_index("entity_mentions_version_id_idx", "entity_mentions", ["version_id"])

    op.create_table(
        "decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("uid", sa.String(), nullable=False, unique=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="accepted"),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("decisions.id")),
        sa.Column("context", sa.Text()),
        sa.Column("decision", sa.Text()),
        sa.Column("consequences", sa.Text()),
        sa.Column("curation_status", sa.String(), nullable=False, server_default="candidate"),
        sa.Column("canonical_record_path", sa.String()),
        sa.Column("source_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("first_seen_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("last_seen_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("record_hash", sa.String()),
        sa.Column("extraction_method", sa.String()),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("decisions_project_status_idx", "decisions", ["project_id", "curation_status"])

    op.create_table(
        "requirements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("uid", sa.String(), nullable=False, unique=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("requirement_id", sa.String()),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("priority", sa.String()),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("curation_status", sa.String(), nullable=False, server_default="candidate"),
        sa.Column("canonical_record_path", sa.String()),
        sa.Column("source_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("first_seen_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("last_seen_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("record_hash", sa.String()),
        sa.Column("extraction_method", sa.String()),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "requirements_project_status_idx",
        "requirements",
        ["project_id", "curation_status"],
    )

    op.create_table(
        "open_questions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text()),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text()),
        sa.Column("resolved_in_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("curation_status", sa.String(), nullable=False, server_default="candidate"),
        sa.Column("canonical_record_path", sa.String()),
        sa.Column("source_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("extraction_method", sa.String()),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "open_questions_project_status_idx",
        "open_questions",
        ["project_id", "curation_status"],
    )


def downgrade() -> None:
    op.drop_index("open_questions_project_status_idx", table_name="open_questions")
    op.drop_table("open_questions")
    op.drop_index("requirements_project_status_idx", table_name="requirements")
    op.drop_table("requirements")
    op.drop_index("decisions_project_status_idx", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("entity_mentions_version_id_idx", table_name="entity_mentions")
    op.drop_index("entity_mentions_chunk_id_idx", table_name="entity_mentions")
    op.drop_index("entity_mentions_entity_id_idx", table_name="entity_mentions")
    op.drop_table("entity_mentions")
    op.drop_table("entities")
