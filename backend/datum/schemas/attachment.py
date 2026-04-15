from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    attachment_uid: str
    filename: str
    content_type: str
    byte_size: int
    content_hash: str
    blob_path: str
    relative_path: str
    created_at: str | None = None


class AttachmentMoveRequest(BaseModel):
    new_relative_path: str
