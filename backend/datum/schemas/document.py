from pydantic import BaseModel


class DocumentCreate(BaseModel):
    relative_path: str
    title: str
    doc_type: str
    content: str
    tags: list[str] | None = None
    status: str = "draft"


class DocumentSave(BaseModel):
    content: str
    base_hash: str


class DocumentMoveRequest(BaseModel):
    new_relative_path: str


class FolderCreateRequest(BaseModel):
    relative_path: str


class GeneratedFileResponse(BaseModel):
    relative_path: str
    absolute_path: str
    size_bytes: int


class DocumentResponse(BaseModel):
    title: str
    doc_type: str
    status: str
    tags: list[str]
    relative_path: str
    version: int
    content_hash: str
    document_uid: str
    created: str | None = None
    updated: str | None = None


class DocumentContentResponse(BaseModel):
    content: str
    metadata: DocumentResponse
