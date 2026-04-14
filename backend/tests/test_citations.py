from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from datum.services.citations import SourceRef, build_citation, resolve_citation


def test_build_citation_includes_human_and_machine_fields():
    chunk = SimpleNamespace(
        id=uuid4(),
        heading_path=["Setup", "Install"],
        start_line=10,
        end_line=25,
    )
    version = SimpleNamespace(version_number=3, content_hash="sha256:abc123")
    document = SimpleNamespace(uid="doc_123", canonical_path="docs/setup.md")
    project = SimpleNamespace(slug="my-project")

    citation = build_citation(chunk, version, document, project, index=2)

    assert citation.index == 2
    assert citation.human_readable == 'my-project/docs/setup.md v3, section "Setup > Install"'
    assert citation.source_ref is not None
    assert citation.source_ref.document_uid == "doc_123"
    assert citation.source_ref.line_start == 10
    assert citation.source_ref.line_end == 25


def test_resolve_citation_reads_main_branch_version_files(tmp_path: Path):
    manifest_dir = tmp_path / ".piq" / "docs" / "setup.md"
    version_dir = manifest_dir / "main"
    version_dir.mkdir(parents=True)
    (version_dir / "v003.md").write_text("a\nb\nc\nd\ne")

    ref = SourceRef(
        project_slug="my-project",
        document_uid="doc_123",
        version_number=3,
        content_hash="sha256:abc123",
        chunk_id="chunk_1",
        canonical_path="docs/setup.md",
        heading_path=["Setup"],
        line_start=2,
        line_end=4,
    )

    assert resolve_citation(ref, manifest_dir) == "b\nc\nd"
