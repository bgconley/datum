from pathlib import Path

from sqlalchemy import BigInteger

from datum.models import (
    DocumentVersion,
    SourceFile,
)
from datum.models.base import Base


def test_all_models_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "pipeline_configs",
        "model_runs",
        "projects",
        "source_files",
        "documents",
        "document_versions",
        "version_head_events",
        "audit_events",
    }
    assert expected.issubset(table_names)


def test_alembic_migration_revision_exists():
    """At least one Alembic revision must be checked in."""
    versions_dir = Path(__file__).parent.parent / "alembic" / "versions"
    assert versions_dir.exists(), "alembic/versions/ directory missing"
    revisions = [f for f in versions_dir.iterdir() if f.suffix == ".py" and f.name != "__pycache__"]
    assert len(revisions) >= 1, "No Alembic migration revisions checked in"


def test_byte_size_columns_are_bigint():
    """Design doc specifies BIGINT for byte_size — verify ORM matches."""
    sf_col = SourceFile.__table__.columns["byte_size"]
    dv_col = DocumentVersion.__table__.columns["byte_size"]
    assert isinstance(
        sf_col.type,
        BigInteger,
    ), f"source_files.byte_size is {sf_col.type}, expected BigInteger"
    assert isinstance(
        dv_col.type,
        BigInteger,
    ), f"document_versions.byte_size is {dv_col.type}, expected BigInteger"


def test_alembic_env_reads_database_url(monkeypatch):
    """Verify alembic env.py reads DATUM_DATABASE_URL from environment."""
    env_path = Path(__file__).parent.parent / "alembic" / "env.py"
    source = env_path.read_text()
    assert "DATUM_DATABASE_URL" in source, "alembic/env.py must read DATUM_DATABASE_URL"


def test_search_models_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "version_texts",
        "document_chunks",
        "chunk_embeddings",
        "technical_terms",
        "ingestion_jobs",
        "search_runs",
        "search_run_results",
    }
    assert expected.issubset(table_names)
