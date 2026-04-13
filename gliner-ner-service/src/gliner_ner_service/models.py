from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1)
    labels: list[str] = Field(min_length=1)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str | None = None


class ExtractedEntity(BaseModel):
    text: str
    label: str
    start: int
    end: int
    score: float


class HealthResponse(BaseModel):
    status: str
    model_id: str
    loaded: bool
    device: str | None = None
