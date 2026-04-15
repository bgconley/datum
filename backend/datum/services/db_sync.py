"""Database catch-up: mirrors filesystem state into Postgres.

Called after every successful filesystem write. The database is derived —
if it falls behind, the reconciler rebuilds it.
"""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import (
    AuditEvent,
    Document,
    DocumentVersion,
    Project,
    SourceFile,
    VersionHeadEvent,
)
from datum.models.operational import Attachment
from datum.models.search import IngestionJob
from datum.services.pipeline_configs import (
    get_extraction_pipeline_config,
    make_ingestion_job_idempotency_key,
)
from datum.services.versioning import VersionInfo


async def sync_project_to_db(
    session: AsyncSession,
    uid: str,
    slug: str,
    name: str,
    filesystem_path: str,
    project_yaml_hash: str,
    description: str | None = None,
    tags: list[str] | None = None,
) -> UUID:
    """Insert or update a project row. Returns the project DB id."""
    result = await session.execute(select(Project).where(Project.uid == uid))
    project = result.scalar_one_or_none()
    if project:
        project.name = name
        project.slug = slug
        project.filesystem_path = filesystem_path
        project.project_yaml_hash = project_yaml_hash
        project.description = description
        project.tags = tags or []
        project.updated_at = datetime.now(UTC)
    else:
        project = Project(
            uid=uid,
            slug=slug,
            name=name,
            description=description,
            tags=tags or [],
            filesystem_path=filesystem_path,
            project_yaml_hash=project_yaml_hash,
        )
        session.add(project)
    await session.flush()
    return project.id


async def sync_document_version_to_db(
    session: AsyncSession,
    project_id: UUID,
    version_info: VersionInfo,
    canonical_path: str,
    title: str,
    doc_type: str,
    status: str,
    tags: list[str],
    change_source: str,
    content_hash: str,
    byte_size: int,
    filesystem_path: str,
) -> None:
    """Insert/update document and version rows after a filesystem write."""
    # Upsert document — always update metadata to track frontmatter changes
    result = await session.execute(
        select(Document).where(Document.uid == version_info.document_uid)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        doc = Document(
            uid=version_info.document_uid,
            project_id=project_id,
            slug=canonical_path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
            canonical_path=canonical_path,
            title=title,
            doc_type=doc_type,
            status=status,
            tags=tags,
        )
        session.add(doc)
        await session.flush()
    else:
        # Update metadata fields on existing document so frontmatter edits propagate
        doc.slug = canonical_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        doc.canonical_path = canonical_path
        doc.title = title
        doc.doc_type = doc_type
        doc.status = status
        doc.tags = tags
        doc.updated_at = datetime.now(UTC)

    # Idempotency: skip if this exact version already exists in DB
    existing_version = await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.version_number == version_info.version_number,
            DocumentVersion.branch == version_info.branch,
        )
    )
    if existing_version.scalar_one_or_none():
        # Version already synced — caller owns transaction commit.
        return

    # Insert version
    version = DocumentVersion(
        document_id=doc.id,
        version_number=version_info.version_number,
        branch=version_info.branch,
        content_hash=content_hash,
        filesystem_path=filesystem_path,
        byte_size=byte_size,
        label=version_info.label,
        change_source=change_source,
        restored_from=version_info.restored_from,
        created_at=version_info.created_at,
    )
    session.add(version)
    await session.flush()

    # Update document.current_version_id
    doc.current_version_id = version.id
    doc.updated_at = datetime.now(UTC)

    # Insert version_head_event
    # Close previous head event
    await session.execute(
        update(VersionHeadEvent)
        .where(
            VersionHeadEvent.document_id == doc.id,
            VersionHeadEvent.branch == version_info.branch,
            VersionHeadEvent.valid_to.is_(None),
        )
        .values(valid_to=version_info.created_at)
    )
    session.add(VersionHeadEvent(
        project_id=project_id,
        document_id=doc.id,
        branch=version_info.branch,
        version_id=version.id,
        canonical_path=canonical_path,
        valid_from=version_info.created_at,
        event_type="save",
    ))

    # Update source_files
    source_file_result = await session.execute(
        select(SourceFile).where(
            SourceFile.project_id == project_id,
            SourceFile.canonical_path == canonical_path,
        )
    )
    sf: SourceFile | None = source_file_result.scalar_one_or_none()
    now = datetime.now(UTC)
    if sf:
        sf.content_hash = content_hash
        sf.byte_size = byte_size
        sf.last_seen_at = now
        sf.indexed_at = now
        sf.deleted_at = None
    else:
        session.add(SourceFile(
            project_id=project_id,
            canonical_path=canonical_path,
            object_kind="document",
            content_hash=content_hash,
            byte_size=byte_size,
            last_seen_at=now,
            indexed_at=now,
        ))

    extraction_config = await get_extraction_pipeline_config(session)
    idem_key = make_ingestion_job_idempotency_key(
        project_id=project_id,
        version_id=version.id,
        job_type="extract",
        content_hash=content_hash,
        pipeline_config_hash=extraction_config.config_hash,
    )
    existing_job = await session.execute(
        select(IngestionJob).where(IngestionJob.idempotency_key == idem_key)
    )
    if existing_job.scalar_one_or_none() is None:
        session.add(
            IngestionJob(
                project_id=project_id,
                version_id=version.id,
                job_type="extract",
                status="queued",
                priority=1,
                pipeline_config_id=extraction_config.id,
                content_hash=content_hash,
                idempotency_key=idem_key,
            )
        )


async def sync_document_move_to_db(
    session: AsyncSession,
    project_id: UUID,
    document_uid: str,
    old_canonical_path: str,
    new_canonical_path: str,
    *,
    version_info: VersionInfo,
    title: str,
    doc_type: str,
    status: str,
    tags: list[str],
    content_hash: str,
    byte_size: int,
    filesystem_path: str,
) -> None:
    """Mirror a filesystem rename as new-save + old-delete lifecycle events."""
    document_result = await session.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.uid == document_uid,
        )
    )
    document = document_result.scalar_one_or_none()
    previous_version_id = document.current_version_id if document is not None else None

    await sync_document_version_to_db(
        session=session,
        project_id=project_id,
        version_info=version_info,
        canonical_path=new_canonical_path,
        title=title,
        doc_type=doc_type,
        status=status,
        tags=tags,
        change_source="rename",
        content_hash=content_hash,
        byte_size=byte_size,
        filesystem_path=filesystem_path,
    )

    if document is None or previous_version_id is None:
        return

    source_file_result = await session.execute(
        select(SourceFile).where(
            SourceFile.project_id == project_id,
            SourceFile.canonical_path == old_canonical_path,
        )
    )
    source_file = source_file_result.scalar_one_or_none()
    if source_file is not None:
        source_file.deleted_at = version_info.created_at
        source_file.last_seen_at = version_info.created_at

    session.add(
        VersionHeadEvent(
            project_id=project_id,
            document_id=document.id,
            branch=version_info.branch,
            version_id=previous_version_id,
            canonical_path=old_canonical_path,
            valid_from=version_info.created_at,
            valid_to=version_info.created_at,
            event_type="delete",
        )
    )


async def soft_delete_document_in_db(
    session: AsyncSession,
    project_id: UUID,
    canonical_path: str,
) -> None:
    """Mark a derived document/source file pair as deleted."""
    deleted_at = datetime.now(UTC)
    document_result = await session.execute(
        select(Document).where(
            Document.project_id == project_id,
            Document.canonical_path == canonical_path,
        )
    )
    document = document_result.scalar_one_or_none()
    delete_events_written = False
    if document is not None:
        document.status = "deleted"
        document.updated_at = deleted_at

        open_head_events = await session.execute(
            select(VersionHeadEvent).where(
                VersionHeadEvent.document_id == document.id,
                VersionHeadEvent.canonical_path == canonical_path,
                VersionHeadEvent.event_type == "save",
                VersionHeadEvent.valid_to.is_(None),
            )
        )
        for head_event in open_head_events.scalars().all():
            head_event.valid_to = deleted_at
            session.add(
                VersionHeadEvent(
                    project_id=project_id,
                    document_id=document.id,
                    branch=head_event.branch,
                    version_id=head_event.version_id,
                    canonical_path=canonical_path,
                    valid_from=deleted_at,
                    valid_to=deleted_at,
                    event_type="delete",
                )
            )
            delete_events_written = True

        if not delete_events_written and document.current_version_id is not None:
            current_version = await session.get(DocumentVersion, document.current_version_id)
            if current_version is not None:
                session.add(
                    VersionHeadEvent(
                        project_id=project_id,
                        document_id=document.id,
                        branch=current_version.branch,
                        version_id=current_version.id,
                        canonical_path=canonical_path,
                        valid_from=deleted_at,
                        valid_to=deleted_at,
                        event_type="delete",
                    )
                )

    source_file_result = await session.execute(
        select(SourceFile).where(
            SourceFile.project_id == project_id,
            SourceFile.canonical_path == canonical_path,
        )
    )
    source_file = source_file_result.scalar_one_or_none()
    if source_file is not None:
        source_file.deleted_at = deleted_at
        source_file.last_seen_at = deleted_at


async def rebuild_document_history_from_manifest(
    session: AsyncSession,
    *,
    project_id: UUID,
    project_slug: str,
    canonical_path: str,
    title: str,
    doc_type: str,
    status: str,
    tags: list[str],
    manifest: dict,
    byte_size: int,
) -> None:
    """Mirror full manifest history into derived tables during import/rebuild flows."""
    from datum.services.manifest_history import ensure_manifest_head_events
    from datum.services.versioning import VersionInfo

    manifest = dict(manifest)
    head_events = ensure_manifest_head_events(manifest)
    version_path_map: dict[tuple[str, int], str] = {}
    for event in head_events:
        if event.get("event_type") != "save":
            continue
        branch_name = str(event.get("branch", "main"))
        version_number = int(event["version"])
        version_path_map[(branch_name, version_number)] = str(
            event.get("canonical_path", canonical_path)
        )

    document_uid = str(manifest["document_uid"])

    ordered_versions: list[tuple[str, dict]] = []
    for branch_name, branch_data in sorted((manifest.get("branches") or {}).items()):
        for version in branch_data.get("versions", []):
            ordered_versions.append((branch_name, version))
    ordered_versions.sort(
        key=lambda item: (
            str(item[1].get("created", "")),
            str(item[0]),
            int(item[1].get("version", 0)),
        )
    )

    for branch_name, version in ordered_versions:
        version_number = int(version["version"])
        created_at = datetime.fromisoformat(str(version["created"]).replace("Z", "+00:00"))
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            created_at = created_at.replace(tzinfo=UTC)
        version_info = VersionInfo(
            version_number=version_number,
            branch=branch_name,
            content_hash=str(version["content_hash"]),
            version_file=str(version["file"]),
            document_uid=document_uid,
            created_at=created_at,
            label=version.get("label"),
            change_source=version.get("change_source"),
            restored_from=version.get("restored_from"),
        )
        await sync_document_version_to_db(
            session=session,
            project_id=project_id,
            version_info=version_info,
            canonical_path=version_path_map.get((branch_name, version_number), canonical_path),
            title=title,
            doc_type=doc_type,
            status=status,
            tags=tags,
            change_source=version_info.change_source or "import",
            content_hash=version_info.content_hash,
            byte_size=byte_size,
            filesystem_path=version_info.version_file,
        )

    document_result = await session.execute(select(Document).where(Document.uid == document_uid))
    document = document_result.scalar_one_or_none()
    if document is None:
        return

    document.slug = canonical_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    document.canonical_path = canonical_path
    document.title = title
    document.doc_type = doc_type
    document.status = status
    document.tags = tags
    document.updated_at = datetime.now(UTC)

    await session.execute(
        delete(VersionHeadEvent).where(VersionHeadEvent.document_id == document.id)
    )

    version_rows = await session.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == document.id)
    )
    versions_by_key = {
        (row.branch, row.version_number): row for row in version_rows.scalars().all()
    }

    latest_version: DocumentVersion | None = None
    latest_created: datetime | None = None
    for event in head_events:
        branch_name = str(event.get("branch", "main"))
        version_number = int(event["version"])
        version = versions_by_key.get((branch_name, version_number))
        if version is None:
            continue
        valid_from = datetime.fromisoformat(str(event["valid_from"]).replace("Z", "+00:00"))
        if valid_from.tzinfo is None or valid_from.utcoffset() is None:
            valid_from = valid_from.replace(tzinfo=UTC)
        raw_valid_to = event.get("valid_to")
        valid_to = None
        if raw_valid_to:
            valid_to = datetime.fromisoformat(str(raw_valid_to).replace("Z", "+00:00"))
            if valid_to.tzinfo is None or valid_to.utcoffset() is None:
                valid_to = valid_to.replace(tzinfo=UTC)

        session.add(
            VersionHeadEvent(
                project_id=project_id,
                document_id=document.id,
                branch=branch_name,
                version_id=version.id,
                canonical_path=str(event.get("canonical_path", canonical_path)),
                valid_from=valid_from,
                valid_to=valid_to,
                event_type=str(event.get("event_type", "save")),
            )
        )

        if event.get("event_type") == "save" and (
            latest_created is None or valid_from >= latest_created
        ):
            latest_created = valid_from
            latest_version = version

    if latest_version is not None:
        document.current_version_id = latest_version.id


async def upsert_attachment_to_db(
    session: AsyncSession,
    *,
    project_id: UUID,
    attachment_uid: str,
    filename: str,
    content_type: str,
    byte_size: int,
    content_hash: str,
    blob_path: str,
    filesystem_path: str,
    metadata: dict,
) -> None:
    result = await session.execute(
        select(Attachment).where(
            Attachment.project_id == project_id,
            Attachment.filesystem_path == filesystem_path,
        )
    )
    attachment = result.scalar_one_or_none()
    payload = dict(metadata)
    payload["attachment_uid"] = attachment_uid
    payload["canonical_path"] = filesystem_path
    if attachment is None:
        attachment = Attachment(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
            content_hash=content_hash,
            blob_path=blob_path,
            filesystem_path=filesystem_path,
            metadata_=payload,
        )
        session.add(attachment)
        return

    attachment.filename = filename
    attachment.content_type = content_type
    attachment.byte_size = byte_size
    attachment.content_hash = content_hash
    attachment.blob_path = blob_path
    attachment.metadata_ = payload


async def move_attachment_in_db(
    session: AsyncSession,
    *,
    project_id: UUID,
    old_filesystem_path: str,
    new_filesystem_path: str,
) -> None:
    result = await session.execute(
        select(Attachment).where(
            Attachment.project_id == project_id,
            Attachment.filesystem_path == old_filesystem_path,
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        return
    attachment.filesystem_path = new_filesystem_path
    metadata = dict(attachment.metadata_ or {})
    metadata["canonical_path"] = new_filesystem_path
    attachment.metadata_ = metadata


async def delete_attachment_in_db(
    session: AsyncSession,
    *,
    project_id: UUID,
    filesystem_path: str,
) -> None:
    result = await session.execute(
        select(Attachment).where(
            Attachment.project_id == project_id,
            Attachment.filesystem_path == filesystem_path,
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        return
    await session.delete(attachment)


async def log_audit_event(
    session: AsyncSession,
    actor_type: str,
    operation: str,
    project_id: UUID | None = None,
    target_path: str | None = None,
    old_hash: str | None = None,
    new_hash: str | None = None,
    actor_name: str | None = None,
    request_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Record an audit event."""
    session.add(AuditEvent(
        actor_type=actor_type,
        actor_name=actor_name,
        operation=operation,
        project_id=project_id,
        target_path=target_path,
        old_hash=old_hash,
        new_hash=new_hash,
        request_id=request_id,
        metadata_=metadata,
    ))
    await session.flush()
