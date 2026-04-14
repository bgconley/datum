from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class AnnotationCreate(BaseModel):
    version_id: str
    annotation_type: str
    content: str | None = None
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> AnnotationCreate:
        if self.start_char is None and self.end_char is None:
            return self
        if self.start_char is None or self.end_char is None:
            raise ValueError("start_char and end_char must both be set or both be null")
        if self.end_char < self.start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        return self


class AnnotationResponse(BaseModel):
    id: str
    version_id: str
    annotation_type: str
    content: str | None = None
    start_char: int | None = None
    end_char: int | None = None
    created_at: datetime | None = None
