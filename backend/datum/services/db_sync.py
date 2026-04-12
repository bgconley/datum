"""Database catch-up: mirrors filesystem state into Postgres.

Called after every successful filesystem write. The database is derived —
if it falls behind, the reconciler rebuilds it.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import (
    AuditEvent,
    Document,
    DocumentVersion,
    Project,
    SourceFile,
    VersionHeadEvent,
)
from datum.models.search import IngestionJob
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
        project.updated_at = datetime.now(timezone.utc)
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
        doc.title = title
        doc.doc_type = doc_type
        doc.status = status
        doc.tags = tags

    # Idempotency: skip if this exact version already exists in DB
    existing_version = await session.execute(
        select(DocumentVersion).where(
            DocumentVersion.document_id == doc.id,
            DocumentVersion.version_number == version_info.version_number,
            DocumentVersion.branch == version_info.branch,
        )
    )
    if existing_version.scalar_one_or_none():
        # Version already synced — just commit any doc metadata updates
        await session.commit()
        return

    # Insert version
    version = DocumentVersion(
        document_id=doc.id,
        version_number=version_info.version_number,
        branch=version_info.branch,
        content_hash=content_hash,
        filesystem_path=filesystem_path,
        byte_size=byte_size,
        change_source=change_source,
        created_at=version_info.created_at,
    )
    session.add(version)
    await session.flush()

    # Update document.current_version_id
    doc.current_version_id = version.id
    doc.updated_at = datetime.now(timezone.utc)

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
        valid_from=version_info.created_at,
        event_type="save",
    ))

    # Update source_files
    result = await session.execute(
        select(SourceFile).where(
            SourceFile.project_id == project_id,
            SourceFile.canonical_path == canonical_path,
        )
    )
    sf = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if sf:
        sf.content_hash = content_hash
        sf.byte_size = byte_size
        sf.last_seen_at = now
        sf.indexed_at = now
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

    idem_key = f"{project_id}:{version.id}:extract:{content_hash}:default:none"
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
                content_hash=content_hash,
                idempotency_key=idem_key,
            )
        )

    await session.commit()


async def log_audit_event(
    session: AsyncSession,
    actor_type: str,
    operation: str,
    project_id: UUID | None = None,
    target_path: str | None = None,
    old_hash: str | None = None,
    new_hash: str | None = None,
    actor_name: str | None = None,
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
    ))
    await session.commit()
