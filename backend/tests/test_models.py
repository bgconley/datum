from datum.models import (
    AuditEvent,
    Document,
    DocumentVersion,
    ModelRun,
    PipelineConfig,
    Project,
    SourceFile,
    VersionHeadEvent,
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
