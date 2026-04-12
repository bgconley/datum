from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datum.models.base import Base, new_uuid, utcnow


class PipelineConfig(Base):
    __tablename__ = "pipeline_configs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("stage", "config_hash"),)


class ModelRun(Base):
    __tablename__ = "model_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String)
    task: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    items_processed: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="active")
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))
    filesystem_path: Mapped[str] = mapped_column(String, nullable=False)
    project_yaml_hash: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="project")


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("projects.id"))
    canonical_path: Mapped[str] = mapped_column(String, nullable=False)
    object_kind: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer)
    mtime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("project_id", "canonical_path"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("projects.id"))
    slug: Mapped[str] = mapped_column(String, nullable=False)
    canonical_path: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    tags: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String))
    current_version_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document")

    __table_args__ = (
        UniqueConstraint("project_id", "canonical_path"),
        UniqueConstraint("project_id", "uid"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"))
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    branch: Mapped[str] = mapped_column(String, default="main")
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    filesystem_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer)
    label: Mapped[Optional[str]] = mapped_column(String)
    change_source: Mapped[Optional[str]] = mapped_column(String)
    agent_name: Mapped[Optional[str]] = mapped_column(String)
    restored_from: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="versions")

    __table_args__ = (UniqueConstraint("document_id", "version_number", "branch"),)


class VersionHeadEvent(Base):
    __tablename__ = "version_head_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    project_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("projects.id"))
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id"))
    branch: Mapped[str] = mapped_column(String, nullable=False)
    version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    actor_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[Optional[str]] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id")
    )
    target_path: Mapped[Optional[str]] = mapped_column(String)
    old_hash: Mapped[Optional[str]] = mapped_column(String)
    new_hash: Mapped[Optional[str]] = mapped_column(String)
    request_id: Mapped[Optional[str]] = mapped_column(String)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
