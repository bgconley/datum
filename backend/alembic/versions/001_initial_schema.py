"""initial schema: Phase 1 tables

Revision ID: 001
Revises:
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pipeline_configs and model_runs first (referenced by other tables)
    op.create_table(
        "pipeline_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("stage", sa.String, nullable=False),
        sa.Column("config_hash", sa.String, nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("stage", "config_hash"),
    )

    op.create_table(
        "model_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_name", sa.String, nullable=False),
        sa.Column("model_version", sa.String),
        sa.Column("task", sa.String, nullable=False),
        sa.Column("config", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("items_processed", sa.Integer),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("uid", sa.String, unique=True, nullable=False),
        sa.Column("slug", sa.String, unique=True, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String, server_default="active"),
        sa.Column("tags", sa.ARRAY(sa.String)),
        sa.Column("filesystem_path", sa.String, nullable=False),
        sa.Column("project_yaml_hash", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "source_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("canonical_path", sa.String, nullable=False),
        sa.Column("object_kind", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("byte_size", sa.BigInteger),
        sa.Column("mtime", sa.DateTime(timezone=True)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("indexed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "canonical_path"),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("uid", sa.String, unique=True, nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("slug", sa.String, nullable=False),
        sa.Column("canonical_path", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("doc_type", sa.String, nullable=False),
        sa.Column("status", sa.String, server_default="draft"),
        sa.Column("tags", sa.ARRAY(sa.String)),
        sa.Column("current_version_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("project_id", "canonical_path"),
        sa.UniqueConstraint("project_id", "uid"),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("parent_version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("branch", sa.String, server_default="main"),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("filesystem_path", sa.String, nullable=False),
        sa.Column("content_type", sa.String),
        sa.Column("byte_size", sa.BigInteger),
        sa.Column("label", sa.String),
        sa.Column("change_source", sa.String),
        sa.Column("agent_name", sa.String),
        sa.Column("restored_from", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_id", "version_number", "branch"),
    )

    op.create_table(
        "version_head_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("branch", sa.String, nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("event_type", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_type", sa.String, nullable=False),
        sa.Column("actor_name", sa.String),
        sa.Column("operation", sa.String, nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id")),
        sa.Column("target_path", sa.String),
        sa.Column("old_hash", sa.String),
        sa.Column("new_hash", sa.String),
        sa.Column("request_id", sa.String),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("version_head_events")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("source_files")
    op.drop_table("projects")
    op.drop_table("model_runs")
    op.drop_table("pipeline_configs")
