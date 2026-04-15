"""Portable project import/export helpers."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from datum.config import settings
from datum.db import async_session_factory
from datum.services.attachment_manager import list_attachments
from datum.services.db_sync import (
    rebuild_document_history_from_manifest,
    sync_project_to_db,
    upsert_attachment_to_db,
)
from datum.services.document_manager import list_documents
from datum.services.filesystem import (
    compute_content_hash,
    ensure_piq_structure,
    read_manifest,
    resolve_manifest_dir,
    write_manifest,
)
from datum.services.manifest_history import (
    deterministic_document_uid,
    ensure_manifest_head_events,
)
from datum.services.project_manager import get_project
from datum.services.versioning import create_version

ConflictStrategy = Literal["skip", "merge", "replace"]


@dataclass
class ExportResult:
    project_slug: str
    bundle_path: Path
    blob_count: int


@dataclass
class ImportResult:
    project_slug: str
    project_path: Path
    imported_documents: int
    imported_attachments: int
    rebuilt_db_state: bool


def export_project_bundle(
    project_slug: str,
    *,
    output_path: Path | None = None,
    include_operational: bool = False,
    projects_root: Path | None = None,
    blobs_root: Path | None = None,
) -> ExportResult:
    projects_root = projects_root or settings.projects_root
    blobs_root = blobs_root or settings.blobs_root
    project = get_project(projects_root, project_slug)
    if project is None:
        raise FileNotFoundError(f"Project '{project_slug}' not found")

    project_path = projects_root / project_slug
    bundle_path = output_path or (Path.cwd() / f"{project_slug}-export")
    if bundle_path.exists():
        raise FileExistsError(f"Export bundle already exists: {bundle_path}")

    bundle_path.mkdir(parents=True)
    shutil.copy2(project_path / "project.yaml", bundle_path / "project.yaml")
    _copy_tree_if_exists(project_path / "docs", bundle_path / "docs")
    _copy_tree_if_exists(project_path / "attachments", bundle_path / "attachments")

    exported_blob_count = _export_blobs(project_path, blobs_root, bundle_path / "blobs")
    _export_piq_state(project_path, bundle_path / ".piq")

    if include_operational:
        _export_operational_dump(bundle_path / "operational.sql")

    return ExportResult(
        project_slug=project_slug,
        bundle_path=bundle_path,
        blob_count=exported_blob_count,
    )


def import_project_bundle(
    bundle_path: Path,
    *,
    conflict_strategy: ConflictStrategy = "merge",
    projects_root: Path | None = None,
    blobs_root: Path | None = None,
    rebuild_db_state: bool = True,
) -> ImportResult:
    projects_root = projects_root or settings.projects_root
    blobs_root = blobs_root or settings.blobs_root
    project_yaml_path = bundle_path / "project.yaml"
    if not project_yaml_path.exists():
        raise FileNotFoundError(f"Bundle is missing project.yaml: {bundle_path}")

    project_data = yaml.safe_load(project_yaml_path.read_text()) or {}
    project_slug = str(project_data.get("slug") or bundle_path.name)
    project_path = projects_root / project_slug
    _prepare_import_destination(project_path, conflict_strategy)

    project_path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_yaml_path, project_path / "project.yaml")
    _copy_tree_if_exists(bundle_path / "docs", project_path / "docs", dirs_exist_ok=True)
    _copy_tree_if_exists(
        bundle_path / "attachments",
        project_path / "attachments",
        dirs_exist_ok=True,
    )
    _copy_tree_if_exists(bundle_path / ".piq", project_path / ".piq", dirs_exist_ok=True)
    _copy_tree_if_exists(bundle_path / "blobs", blobs_root, dirs_exist_ok=True)

    ensure_piq_structure(project_path)
    if not (project_path / ".piq" / "manifest.yaml").exists():
        write_manifest(project_path / ".piq" / "manifest.yaml", {"documents": []})

    _ensure_document_manifests(project_path, project_slug)

    rebuilt = False
    if rebuild_db_state:
        asyncio.run(_rebuild_project_db_state(project_path, project_slug))
        rebuilt = True

    return ImportResult(
        project_slug=project_slug,
        project_path=project_path,
        imported_documents=len(list_documents(project_path)),
        imported_attachments=len(list_attachments(project_path)),
        rebuilt_db_state=rebuilt,
    )


def _copy_tree_if_exists(
    source: Path,
    destination: Path,
    *,
    dirs_exist_ok: bool = False,
) -> None:
    if not source.exists():
        return
    shutil.copytree(source, destination, dirs_exist_ok=dirs_exist_ok)


def _export_blobs(project_path: Path, blobs_root: Path, bundle_blobs_root: Path) -> int:
    count = 0
    for attachment in list_attachments(project_path):
        source = blobs_root / attachment.blob_path
        if not source.exists():
            continue
        destination = bundle_blobs_root / attachment.blob_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        shutil.copy2(source, destination)
        count += 1
    return count


def _export_piq_state(project_path: Path, bundle_piq_root: Path) -> None:
    bundle_piq_root.mkdir(parents=True, exist_ok=True)
    _copy_if_exists(project_path / ".piq" / "manifest.yaml", bundle_piq_root / "manifest.yaml")
    _copy_tree_if_exists(project_path / ".piq" / "docs", bundle_piq_root / "docs")
    _copy_tree_if_exists(project_path / ".piq" / "records", bundle_piq_root / "records")
    _copy_tree_if_exists(
        project_path / ".piq" / "project" / "versions",
        bundle_piq_root / "project" / "versions",
    )
    _copy_if_exists(project_path / ".piq" / "snapshots.yaml", bundle_piq_root / "snapshots.yaml")
    if (project_path / ".piq" / "branches.yaml").exists():
        _copy_if_exists(project_path / ".piq" / "branches.yaml", bundle_piq_root / "branches.yaml")
    elif (project_path / ".piq" / "active-branches.yaml").exists():
        _copy_if_exists(
            project_path / ".piq" / "active-branches.yaml",
            bundle_piq_root / "branches.yaml",
        )


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _prepare_import_destination(project_path: Path, conflict_strategy: ConflictStrategy) -> None:
    if not project_path.exists():
        return
    if conflict_strategy == "skip":
        raise FileExistsError(f"Project already exists: {project_path}")
    if conflict_strategy == "replace":
        shutil.rmtree(project_path)
        return
    if conflict_strategy != "merge":
        raise ValueError(f"Unsupported conflict strategy: {conflict_strategy}")


def _ensure_document_manifests(project_path: Path, project_slug: str) -> None:
    docs_root = project_path / "docs"
    if not docs_root.exists():
        return

    for document in list_documents(project_path):
        manifest_dir = resolve_manifest_dir(project_path, document.relative_path, for_write=False)
        manifest_path = manifest_dir / "manifest.yaml"
        manifest = read_manifest(manifest_path)
        if not manifest:
            content = (project_path / document.relative_path).read_bytes()
            create_version(
                project_path=project_path,
                canonical_path=document.relative_path,
                content=content,
                change_source="import",
                document_uid=deterministic_document_uid(project_slug, document.relative_path),
            )
            manifest = read_manifest(manifest_path)
        if not manifest.get("document_uid"):
            manifest["document_uid"] = deterministic_document_uid(
                project_slug,
                document.relative_path,
            )
        ensure_manifest_head_events(manifest)
        write_manifest(manifest_path, manifest)


async def _rebuild_project_db_state(project_path: Path, project_slug: str) -> None:
    project_info = get_project(project_path.parent, project_slug)
    if project_info is None:
        raise FileNotFoundError(f"Imported project missing project.yaml: {project_slug}")

    project_yaml = (project_path / "project.yaml").read_bytes()

    async with async_session_factory() as session:
        project_id = await sync_project_to_db(
            session=session,
            uid=project_info.uid,
            slug=project_info.slug,
            name=project_info.name,
            filesystem_path=str(project_path),
            project_yaml_hash=compute_content_hash(project_yaml),
            description=project_info.description,
            tags=project_info.tags,
        )

        for document in list_documents(project_path):
            manifest_dir = resolve_manifest_dir(
                project_path,
                document.relative_path,
                for_write=False,
            )
            manifest = read_manifest(manifest_dir / "manifest.yaml")
            if not manifest:
                continue
            await rebuild_document_history_from_manifest(
                session=session,
                project_id=project_id,
                project_slug=project_slug,
                canonical_path=document.relative_path,
                title=document.title,
                doc_type=document.doc_type,
                status=document.status,
                tags=document.tags,
                manifest=manifest,
                byte_size=len((project_path / document.relative_path).read_bytes()),
            )

        for attachment in list_attachments(project_path):
            metadata_path = project_path / attachment.relative_path
            metadata = yaml.safe_load(metadata_path.read_text()) or {}
            await upsert_attachment_to_db(
                session=session,
                project_id=project_id,
                attachment_uid=attachment.attachment_uid,
                filename=attachment.filename,
                content_type=attachment.content_type,
                byte_size=attachment.byte_size,
                content_hash=attachment.content_hash,
                blob_path=attachment.blob_path,
                filesystem_path=attachment.relative_path,
                metadata=metadata,
            )

        await session.commit()


def _export_operational_dump(output_path: Path) -> None:
    database_url = settings.database_url.replace("+asyncpg", "")
    command = ["pg_dump", "--data-only", "--inserts", "--file", str(output_path), database_url]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("pg_dump is required for --include-operational") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr or exc.stdout or "pg_dump failed") from exc
