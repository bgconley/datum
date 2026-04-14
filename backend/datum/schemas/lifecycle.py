from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SessionStartRequest(BaseModel):
    session_id: str
    project_slug: str | None = None
    client_type: str = "generic"


class SessionStartResponse(BaseModel):
    id: str
    session_id: str
    project_id: str | None
    client_type: str
    status: str
    enforcement_mode: str
    is_dirty: bool
    started_at: datetime


class PreflightRequest(BaseModel):
    action: Literal["get_project_context", "search_project_memory", "list_candidates"]


class PreflightResponse(BaseModel):
    recorded: bool
    action: str
    session_id: str


class DeltaRequest(BaseModel):
    delta_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
    summary_text: str | None = None


class DeltaResponse(BaseModel):
    id: str
    delta_type: str
    detail: dict[str, Any]
    flushed: bool
    created_at: datetime


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    enforcement_mode: str
    is_dirty: bool
    dirty_reasons: dict[str, int] | None
    last_preflight_at: datetime | None
    last_preflight_action: str | None
    last_flush_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    unflushed_delta_count: int


class FlushSummaryResponse(BaseModel):
    counts: dict[str, int]
    recent_paths: list[str]
    recent_commands: list[str]


class FlushResponse(BaseModel):
    flushed_count: int
    session_id: str
    summary: FlushSummaryResponse | None = None
    session_note_path: str | None = None


class FinalizeResponse(BaseModel):
    session_id: str
    status: str
    ended_at: datetime | None
