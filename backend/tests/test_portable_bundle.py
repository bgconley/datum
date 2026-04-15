from __future__ import annotations

from pathlib import Path

import yaml

from datum.cli import main as root_cli
from datum.config import settings
from datum.services.portable_bundle import export_project_bundle, import_project_bundle
from datum.services.project_manager import create_project
from datum.services.versioning import create_version


def _write_attachment(project_path: Path, blobs_root: Path) -> tuple[str, str]:
    blob_rel = "aa/bb/test-blob.bin"
    blob_path = blobs_root / blob_rel
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(b"attachment-bytes")

    metadata_path = project_path / "attachments" / "diagram" / "metadata.yaml"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "attachment_uid": "att_test",
                "filename": "diagram.png",
                "content_type": "image/png",
                "size_bytes": 16,
                "blob_ref": "sha256:test-blob",
                "blob_path": blob_rel,
                "canonical_path": "attachments/diagram/metadata.yaml",
                "created_at": "2026-04-14T00:00:00+00:00",
            },
            sort_keys=False,
        )
    )
    return metadata_path.relative_to(project_path).as_posix(), blob_rel


def test_export_import_round_trip_preserves_bundle_layout_and_files(tmp_path):
    source_projects = tmp_path / "source-projects"
    source_projects.mkdir()
    source_blobs = tmp_path / "source-blobs"
    source_blobs.mkdir()

    create_project(source_projects, "Portable", "portable")
    project_path = source_projects / "portable"
    create_version(
        project_path=project_path,
        canonical_path="docs/overview.md",
        content=b"---\ntitle: Overview\ntype: plan\nstatus: active\n---\n# Overview\n",
        change_source="web",
    )
    create_version(
        project_path=project_path,
        canonical_path="docs/overview.md",
        content=b"---\ntitle: Overview\ntype: plan\nstatus: active\n---\n# Overview v2\n",
        change_source="web",
    )
    attachment_path, blob_rel = _write_attachment(project_path, source_blobs)

    (project_path / ".piq" / "records").mkdir(parents=True, exist_ok=True)
    (project_path / ".piq" / "records" / "decision.yaml").write_text(
        "decision: keep import-export\n"
    )
    (project_path / ".piq" / "snapshots.yaml").write_text(
        yaml.safe_dump(
            {
                "snapshots": {
                    "release-v1": {
                        "documents": {
                            "docs/overview.md": "sha256:placeholder",
                        }
                    }
                }
            },
            sort_keys=False,
        )
    )
    (project_path / ".piq" / "branches.yaml").write_text(
        yaml.safe_dump({"branches": {"release": {"head": 2}}}, sort_keys=False)
    )

    bundle_path = tmp_path / "portable-bundle"
    exported = export_project_bundle(
        "portable",
        output_path=bundle_path,
        projects_root=source_projects,
        blobs_root=source_blobs,
    )

    assert exported.project_slug == "portable"
    assert (bundle_path / "project.yaml").exists()
    assert (bundle_path / "docs" / "overview.md").exists()
    assert (bundle_path / attachment_path).exists()
    assert (bundle_path / "blobs" / blob_rel).exists()
    assert (bundle_path / ".piq" / "docs" / "overview.md" / "manifest.yaml").exists()
    assert (bundle_path / ".piq" / "records" / "decision.yaml").exists()
    assert (bundle_path / ".piq" / "snapshots.yaml").exists()
    assert (bundle_path / ".piq" / "branches.yaml").exists()

    target_projects = tmp_path / "target-projects"
    target_projects.mkdir()
    target_blobs = tmp_path / "target-blobs"
    target_blobs.mkdir()

    imported = import_project_bundle(
        bundle_path,
        projects_root=target_projects,
        blobs_root=target_blobs,
        rebuild_db_state=False,
    )

    imported_project = target_projects / "portable"
    assert imported.project_slug == "portable"
    assert imported.project_path == imported_project
    assert imported.imported_documents == 1
    assert imported.imported_attachments == 1
    assert imported.rebuilt_db_state is False
    assert (imported_project / "docs" / "overview.md").exists()
    assert (imported_project / attachment_path).exists()
    assert (target_blobs / blob_rel).exists()
    assert (imported_project / ".piq" / "docs" / "overview.md" / "manifest.yaml").exists()
    assert (imported_project / ".piq" / "records" / "decision.yaml").exists()


def test_import_bundle_reports_rebuilt_db_state_when_requested(tmp_path, monkeypatch):
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    blobs_root = tmp_path / "blobs"
    blobs_root.mkdir()

    create_project(projects_root, "Portable", "portable")
    project_path = projects_root / "portable"
    create_version(
        project_path=project_path,
        canonical_path="docs/overview.md",
        content=b"---\ntitle: Overview\ntype: plan\nstatus: active\n---\n# Overview\n",
        change_source="web",
    )

    bundle_path = tmp_path / "portable-bundle"
    export_project_bundle(
        "portable",
        output_path=bundle_path,
        projects_root=projects_root,
        blobs_root=blobs_root,
    )

    rebuilt: list[tuple[Path, str]] = []

    async def fake_rebuild(project_path: Path, project_slug: str) -> None:
        rebuilt.append((project_path, project_slug))

    monkeypatch.setattr("datum.services.portable_bundle._rebuild_project_db_state", fake_rebuild)

    target_projects = tmp_path / "target-projects"
    target_projects.mkdir()
    target_blobs = tmp_path / "target-blobs"
    target_blobs.mkdir()

    imported = import_project_bundle(
        bundle_path,
        projects_root=target_projects,
        blobs_root=target_blobs,
        rebuild_db_state=True,
    )

    assert imported.rebuilt_db_state is True
    assert rebuilt == [(target_projects / "portable", "portable")]


def test_root_cli_dispatches_portable_commands(monkeypatch, capsys):
    settings.projects_root = Path("/tmp/source-projects")
    settings.blobs_root = Path("/tmp/source-blobs")

    monkeypatch.setattr(
        "datum.cli.portable.export_project_bundle",
        lambda project_slug, **kwargs: type(
            "Result",
            (),
            {"bundle_path": Path(f"/tmp/{project_slug}-bundle")},
        )(),
    )
    monkeypatch.setattr(
        "datum.cli.portable.import_project_bundle",
        lambda bundle_path, **kwargs: type(
            "Result",
            (),
            {"project_path": Path(bundle_path) / "portable"},
        )(),
    )

    root_cli.main(["export", "portable"])
    assert capsys.readouterr().out.strip() == "/tmp/portable-bundle"

    root_cli.main(["import", "/tmp/bundle"])
    assert capsys.readouterr().out.strip() == "/tmp/bundle/portable"
