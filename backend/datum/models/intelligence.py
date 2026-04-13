from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from datum.models.base import Base, new_uuid, utcnow


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("entity_type", "canonical_name"),)


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    entity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE")
    )
    version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_method: Mapped[str] = mapped_column(String, nullable=False)
    model_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    text_start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    text_end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="accepted")
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("decisions.id")
    )
    context: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str | None] = mapped_column(Text)
    consequences: Mapped[str | None] = mapped_column(Text)
    curation_status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    canonical_record_path: Mapped[str | None] = mapped_column(String)
    source_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    first_seen_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    last_seen_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str | None] = mapped_column(String)
    extraction_method: Mapped[str | None] = mapped_column(String)
    model_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    uid: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    requirement_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    curation_status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    canonical_record_path: Mapped[str | None] = mapped_column(String)
    source_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    first_seen_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    last_seen_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str | None] = mapped_column(String)
    extraction_method: Mapped[str | None] = mapped_column(String)
    model_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpenQuestion(Base):
    __tablename__ = "open_questions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_in_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    curation_status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    canonical_record_path: Mapped[str | None] = mapped_column(String)
    source_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_versions.id")
    )
    extraction_method: Mapped[str | None] = mapped_column(String)
    model_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("model_runs.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow)
