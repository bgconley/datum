from pathlib import Path

import pytest

from datum.services.document_manager import create_document
from datum.services.ingestion import (
    IngestionContext,
    run_chunking,
    run_extraction,
    run_technical_terms,
)
from datum.services.project_manager import create_project


@pytest.fixture
def project_with_doc(tmp_path: Path):
    create_project(tmp_path, "Test", "test")
    project = tmp_path / "test"
    create_document(
        project,
        "docs/arch.md",
        "Architecture",
        "plan",
        (
            "# Architecture\n\n## API Layer\n\n"
            "The API runs on port 8001 at /api/v1/users.\n\n"
            "## Database\n\nPostgreSQL with DATABASE_URL connection."
        ),
    )
    return project


class TestRunExtraction:
    def test_extracts_text(self, project_with_doc: Path):
        ctx = IngestionContext(project_path=project_with_doc, canonical_path="docs/arch.md")
        result = run_extraction(ctx)
        assert result is not None
        assert "API Layer" in result.content
        assert "PostgreSQL" in result.content

    def test_strips_frontmatter(self, project_with_doc: Path):
        ctx = IngestionContext(project_path=project_with_doc, canonical_path="docs/arch.md")
        result = run_extraction(ctx)
        assert result is not None
        assert "title:" not in result.content


class TestRunChunking:
    def test_produces_chunks(self, project_with_doc: Path):
        ctx = IngestionContext(project_path=project_with_doc, canonical_path="docs/arch.md")
        extraction = run_extraction(ctx)
        assert extraction is not None
        chunks = run_chunking(extraction.content)
        assert len(chunks) >= 2
        assert chunks[0].heading_path == ["Architecture"]

    def test_chunks_have_offsets(self, project_with_doc: Path):
        ctx = IngestionContext(project_path=project_with_doc, canonical_path="docs/arch.md")
        extraction = run_extraction(ctx)
        assert extraction is not None
        chunks = run_chunking(extraction.content)
        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char


class TestRunTechnicalTerms:
    def test_extracts_terms(self, project_with_doc: Path):
        ctx = IngestionContext(project_path=project_with_doc, canonical_path="docs/arch.md")
        extraction = run_extraction(ctx)
        assert extraction is not None
        terms = run_technical_terms(extraction.content)
        env_vars = [term for term in terms if term.term_type == "env_var"]
        assert any("DATABASE_URL" in term.raw_text for term in env_vars)
