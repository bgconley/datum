from pydantic import BaseModel

from datum.schemas.document import DocumentResponse, GeneratedFileResponse


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
    filesystem_path: str | None = None


class WorkspaceSnapshotResponse(BaseModel):
    project: ProjectResponse
    documents: list[DocumentResponse]
    generated_files: list[GeneratedFileResponse]
