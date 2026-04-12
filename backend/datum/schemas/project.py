from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    tags: list[str] | None = None


class ProjectResponse(BaseModel):
    uid: str
    slug: str
    name: str
    description: str | None = None
    status: str
    tags: list[str]
    created: str | None = None
