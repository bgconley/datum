"""Schemas for agent-facing REST API surfaces."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    session_id: str
    agent_name: str
    summary: str
    content: str = ""
    repo_path: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    files_touched: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class SessionAppendRequest(BaseModel):
    content: str
    files_touched: list[str] = Field(default_factory=list)
    commands_run: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    summary: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    path: str
    agent_name: str
    summary: str


class SessionListItem(BaseModel):
    session_id: str
    agent_name: str
    summary: str
    path: str
    started_at: str | None = None
    ended_at: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionListItem] = Field(default_factory=list)


class SourceRefSchema(BaseModel):
    project_slug: str
    document_uid: str
    version_number: int
    content_hash: str
    chunk_id: str
    canonical_path: str
    heading_path: list[str] = Field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


class CitationResolveRequest(BaseModel):
    source_ref: SourceRefSchema


class CitationResolveResponse(BaseModel):
    content: str | None = None
    content_kind: str | None = None
    trusted_for: list[str] = Field(default_factory=list)
    not_trusted_for: list[str] = Field(default_factory=list)
    error: str | None = None


class AuditEventResponse(BaseModel):
    id: str
    actor_type: str
    actor_name: str | None = None
    operation: str
    target_path: str | None = None
    created_at: datetime
    metadata: dict | None = None


class AuditListResponse(BaseModel):
    events: list[AuditEventResponse] = Field(default_factory=list)
    count: int


class ApiKeyCreateRequest(BaseModel):
    name: str
    scope: str
    expires_days: int | None = None


class ApiKeyCreateResponse(BaseModel):
    key: str
    key_id: str
    name: str
    scope: str
    prefix: str


class ApiKeyListItem(BaseModel):
    key_id: str
    name: str
    scope: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool
    expires_at: datetime | None = None


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyListItem] = Field(default_factory=list)
