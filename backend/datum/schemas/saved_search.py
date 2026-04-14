from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SavedSearchCreate(BaseModel):
    name: str
    query_text: str
    filters: dict[str, Any] | None = None


class SavedSearchResponse(BaseModel):
    id: str
    name: str
    query_text: str
    filters: dict[str, Any] | None = None
    project_id: str | None = None
    created_at: datetime | None = None
