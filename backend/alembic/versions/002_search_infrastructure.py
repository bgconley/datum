"""search infrastructure: Phase 2 tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "version_texts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("text_kind", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("extraction_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("heading_path", sa.ARRAY(sa.String())),
        sa.Column("start_line", sa.Integer()),
        sa.Column("end_line", sa.Integer()),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer()),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("chunking_run_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id")),
        sa.Column("source_text_hash", sa.String(), nullable=False),
        sa.UniqueConstraint("version_id", "chunk_index"),
    )

    op.create_table(
        "chunk_embeddings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("document_chunks.id"), nullable=False),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id"), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("chunk_id", "model_run_id"),
    )

    op.create_table(
        "technical_terms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("normalized_text", sa.String(), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("term_type", sa.String(), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("document_chunks.id")),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("extraction_method", sa.String(), nullable=False),
        sa.Column("pipeline_config_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id")),
        sa.Column("confidence", sa.Float()),
        sa.Column("source_text_hash", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id")),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), server_default="queued", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="2", nullable=False),
        sa.Column("pipeline_config_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id")),
        sa.Column("model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("content_hash", sa.String()),
        sa.Column("idempotency_key", sa.String(), unique=True),
        sa.Column("depends_on", sa.ARRAY(UUID(as_uuid=True))),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "search_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("parsed_query", JSONB),
        sa.Column("version_scope", sa.String()),
        sa.Column("project_scope", sa.String()),
        sa.Column("retrieval_config_id", UUID(as_uuid=True), sa.ForeignKey("pipeline_configs.id")),
        sa.Column("embedding_model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("reranker_model_run_id", UUID(as_uuid=True), sa.ForeignKey("model_runs.id")),
        sa.Column("result_count", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "search_run_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("search_run_id", UUID(as_uuid=True), sa.ForeignKey("search_runs.id"), nullable=False),
        sa.Column("chunk_id", UUID(as_uuid=True), sa.ForeignKey("document_chunks.id"), nullable=False),
        sa.Column("rank_bm25", sa.Integer()),
        sa.Column("rank_vector", sa.Integer()),
        sa.Column("rank_entity", sa.Integer()),
        sa.Column("fused_score", sa.Float()),
        sa.Column("rerank_score", sa.Float()),
        sa.Column("final_rank", sa.Integer()),
        sa.UniqueConstraint("search_run_id", "chunk_id"),
    )

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    op.execute(
        """
        ALTER TABLE chunk_embeddings
        ADD COLUMN IF NOT EXISTS embedding halfvec(1024) NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunks_bm25_idx
        ON document_chunks USING bm25 (id, content)
        WITH (key_field='id')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS chunk_embeddings_hnsw_idx
        ON chunk_embeddings USING hnsw (embedding halfvec_cosine_ops)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS technical_terms_normalized_idx ON technical_terms(normalized_text)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS technical_terms_type_idx ON technical_terms(term_type, normalized_text)"
    )


def downgrade() -> None:
    op.drop_table("search_run_results")
    op.drop_table("search_runs")
    op.drop_table("ingestion_jobs")
    op.drop_table("technical_terms")
    op.drop_table("chunk_embeddings")
    op.drop_table("document_chunks")
    op.drop_table("version_texts")
