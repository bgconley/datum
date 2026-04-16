from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from datum.models.base import Base, new_uuid, utcnow


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    client_type: Mapped[str] = mapped_column(String, nullable=False, default="generic")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    enforcement_mode: Mapped[str] = mapped_column(String, nullable=False, default="advisory")
    is_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    dirty_reasons: Mapped[dict | None] = mapped_column(JSONB)
    last_preflight_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_preflight_action: Mapped[str | None] = mapped_column(String)
    last_flush_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    deltas: Mapped[list[SessionDelta]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    hook_events: Mapped[list[HookEvent]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class SessionDelta(Base):
    __tablename__ = "session_deltas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agent_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    delta_type: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text)
    flushed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[AgentSession] = relationship(back_populates="deltas")


class HookEvent(Base):
    __tablename__ = "hook_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agent_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hook_type: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    session: Mapped[AgentSession] = relationship(back_populates="hook_events")
