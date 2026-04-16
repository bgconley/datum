"""Pydantic response models for dashboard endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    name: str
    healthy: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    subsystems: list[HealthStatus]
    healthy: bool
    checked_at: datetime


class IngestionStats(BaseModel):
    queued: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    total: int = 0


class AgentActivityStats(BaseModel):
    sessions_active: int = 0
    sessions_total: int = 0
    hook_event_counts: dict[str, int] = Field(default_factory=dict)
    mcp_op_counts: dict[str, int] = Field(default_factory=dict)


class ActivityEvent(BaseModel):
    id: UUID
    actor_type: str
    operation: str
    target_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SessionSummary(BaseModel):
    id: UUID
    session_id: str
    client_type: str
    status: str
    enforcement_mode: str
    is_dirty: bool
    delta_count: int = 0
    started_at: datetime
    ended_at: datetime | None = None


class HookEventResponse(BaseModel):
    id: UUID
    hook_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SessionDetail(BaseModel):
    id: UUID
    session_id: str
    client_type: str
    status: str
    enforcement_mode: str
    is_dirty: bool
    delta_count: int = 0
    started_at: datetime
    ended_at: datetime | None = None
    deltas: list[dict[str, Any]] = Field(default_factory=list)
    hook_events: list[HookEventResponse] = Field(default_factory=list)
    audit_events: list[ActivityEvent] = Field(default_factory=list)


class HookEventCreate(BaseModel):
    hook_type: str
    detail: dict[str, Any] = Field(default_factory=dict)
