from pydantic import BaseModel


class VersionResponse(BaseModel):
    version_number: int
    branch: str
    content_hash: str
    version_file: str
    document_uid: str
    created_at: str
    label: str | None = None
    change_source: str | None = None
    restored_from: int | None = None
    created_by: str | None = None
    indexing_status: str | None = None


class VersionContentResponse(BaseModel):
    version_number: int
    content: str
    content_hash: str


class VersionDiffResponse(BaseModel):
    version_a: int
    version_b: int
    diff_text: str
    additions: int
    deletions: int


class VersionRestoreRequest(BaseModel):
    label: str | None = None
