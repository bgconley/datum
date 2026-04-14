"""phase 8 operational tables

Revision ID: 009
Revises: 008
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("filters", JSONB),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("saved_searches_project_created_idx", "saved_searches", ["project_id", "created_at"])

    op.create_table(
        "collections",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("collections_project_created_idx", "collections", ["project_id", "created_at"])

    op.create_table(
        "collection_members",
        sa.Column(
            "collection_id",
            UUID(as_uuid=True),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("collection_members_document_idx", "collection_members", ["document_id"])

    op.create_table(
        "annotations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("annotation_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("start_char", sa.Integer()),
        sa.Column("end_char", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("annotations_version_created_idx", "annotations", ["version_id", "created_at"])

    op.create_table(
        "attachments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_type", sa.String()),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("blob_path", sa.String(), nullable=False),
        sa.Column("filesystem_path", sa.String(), nullable=False),
        sa.Column("extracted_text_hash", sa.String()),
        sa.Column("thumbnail_path", sa.String()),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "filesystem_path"),
    )
    op.create_index("attachments_project_created_idx", "attachments", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("attachments_project_created_idx", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("annotations_version_created_idx", table_name="annotations")
    op.drop_table("annotations")
    op.drop_index("collection_members_document_idx", table_name="collection_members")
    op.drop_table("collection_members")
    op.drop_index("collections_project_created_idx", table_name="collections")
    op.drop_table("collections")
    op.drop_index("saved_searches_project_created_idx", table_name="saved_searches")
    op.drop_table("saved_searches")
