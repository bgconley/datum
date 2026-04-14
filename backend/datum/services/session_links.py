"""Session-note document auto-linking helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import Document
from datum.models.intelligence import DocumentLink
from datum.services.sessions import detect_session_document_links


async def auto_link_session_note(
    session: AsyncSession,
    *,
    project_id: UUID,
    version_id: UUID,
    content: str,
) -> int:
    result = await session.execute(
        select(Document).where(Document.project_id == project_id)
    )
    documents = result.scalars().all()
    doc_by_path = {document.canonical_path: document for document in documents}
    links = detect_session_document_links(content, set(doc_by_path))

    await session.execute(
        delete(DocumentLink).where(
            DocumentLink.source_version_id == version_id,
            DocumentLink.auto_detected.is_(True),
        )
    )

    created = 0
    for link in links:
        target_document = doc_by_path.get(link.target_path)
        if target_document is None:
            continue
        session.add(
            DocumentLink(
                source_version_id=version_id,
                target_document_id=target_document.id,
                target_version_id=target_document.current_version_id,
                link_type=link.link_type,
                anchor_text=link.anchor_text,
                auto_detected=True,
                confidence=link.confidence,
            )
        )
        created += 1
    await session.flush()
    return created
