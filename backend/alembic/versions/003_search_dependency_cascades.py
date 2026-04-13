"""search dependency cascades

Revision ID: 003
Revises: 002
Create Date: 2026-04-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("version_texts_version_id_fkey", "version_texts", type_="foreignkey")
    op.create_foreign_key(
        "version_texts_version_id_fkey",
        "version_texts",
        "document_versions",
        ["version_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("document_chunks_version_id_fkey", "document_chunks", type_="foreignkey")
    op.create_foreign_key(
        "document_chunks_version_id_fkey",
        "document_chunks",
        "document_versions",
        ["version_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("chunk_embeddings_chunk_id_fkey", "chunk_embeddings", type_="foreignkey")
    op.create_foreign_key(
        "chunk_embeddings_chunk_id_fkey",
        "chunk_embeddings",
        "document_chunks",
        ["chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("technical_terms_chunk_id_fkey", "technical_terms", type_="foreignkey")
    op.create_foreign_key(
        "technical_terms_chunk_id_fkey",
        "technical_terms",
        "document_chunks",
        ["chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("technical_terms_version_id_fkey", "technical_terms", type_="foreignkey")
    op.create_foreign_key(
        "technical_terms_version_id_fkey",
        "technical_terms",
        "document_versions",
        ["version_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("technical_terms_version_id_fkey", "technical_terms", type_="foreignkey")
    op.create_foreign_key(
        "technical_terms_version_id_fkey",
        "technical_terms",
        "document_versions",
        ["version_id"],
        ["id"],
    )

    op.drop_constraint("technical_terms_chunk_id_fkey", "technical_terms", type_="foreignkey")
    op.create_foreign_key(
        "technical_terms_chunk_id_fkey",
        "technical_terms",
        "document_chunks",
        ["chunk_id"],
        ["id"],
    )

    op.drop_constraint("chunk_embeddings_chunk_id_fkey", "chunk_embeddings", type_="foreignkey")
    op.create_foreign_key(
        "chunk_embeddings_chunk_id_fkey",
        "chunk_embeddings",
        "document_chunks",
        ["chunk_id"],
        ["id"],
    )

    op.drop_constraint("document_chunks_version_id_fkey", "document_chunks", type_="foreignkey")
    op.create_foreign_key(
        "document_chunks_version_id_fkey",
        "document_chunks",
        "document_versions",
        ["version_id"],
        ["id"],
    )

    op.drop_constraint("version_texts_version_id_fkey", "version_texts", type_="foreignkey")
    op.create_foreign_key(
        "version_texts_version_id_fkey",
        "version_texts",
        "document_versions",
        ["version_id"],
        ["id"],
    )
