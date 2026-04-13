"""Document lifecycle management.

Documents are filesystem-first: the .md/.sql/.yaml file on disk is canonical.
Frontmatter stores human metadata. Hashes and versions live in .piq/ manifests.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from datum.services.filesystem import (
    compute_content_hash,
    validate_canonical_path,
)
from datum.services.versioning import (
    VersionInfo,
    create_version,
    get_current_version,
)

# Document paths must live under docs/ per design doc filesystem schema.
# project.yaml, attachments/, and .piq/ have separate semantics.
_ALLOWED_DOC_PREFIXES = ("docs/",)


class ConflictError(Exception):
    """Raised when a save conflicts with the current file state."""
    def __init__(self, current_hash: str, base_hash: str):
        self.current_hash = current_hash
        self.base_hash = base_hash
        super().__init__(f"Conflict: file changed (current={current_hash}, base={base_hash})")


def _validate_document_path(relative_path: str) -> str:
    """Enforce that document paths live under docs/ and return the normalized path."""
    resolved = validate_canonical_path(relative_path)
    normalized_path = resolved.as_posix()
    if len(resolved.parts) < 2 or not any(
        normalized_path.startswith(prefix) for prefix in _ALLOWED_DOC_PREFIXES
    ):
        raise ValueError(
            f"Document path must be under docs/, got: {relative_path}"
        )
    return normalized_path


@dataclass
class DocumentInfo:
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


def create_document(
    project_path: Path,
    relative_path: str,
    title: str,
    doc_type: str,
    content: str,
    tags: list[str] | None = None,
    status: str = "draft",
) -> DocumentInfo:
    """Create a new document with frontmatter and initial version.

    Raises ValueError if path is not under docs/ or already exists.
    """
    normalized_path = _validate_document_path(relative_path)

    # Reject if canonical file already exists
    canonical_full = project_path / normalized_path
    if canonical_full.exists():
        raise FileExistsError(f"Document already exists: {normalized_path}")

    now = datetime.now(UTC).strftime("%Y-%m-%d")

    # Build frontmatter + content
    fm = frontmatter.Post(
        content,
        title=title,
        type=doc_type,
        status=status,
        created=now,
        updated=now,
    )
    if tags:
        fm["tags"] = tags

    file_bytes = frontmatter.dumps(fm).encode()

    # create_version owns the canonical write transaction.
    # It writes: pending_commit -> version file -> canonical file -> final manifest.
    # Do NOT write the canonical file here — that bypasses the pending_commit protocol.
    version_info = create_version(
        project_path=project_path,
        canonical_path=normalized_path,
        content=file_bytes,
        change_source="web",
    )
    if version_info is None:
        raise RuntimeError(f"Initial version was not created for {normalized_path}")

    return DocumentInfo(
        title=title,
        doc_type=doc_type,
        status=status,
        tags=tags or [],
        relative_path=normalized_path,
        version=version_info.version_number,
        content_hash=version_info.content_hash,
        document_uid=version_info.document_uid,
        created=now,
        updated=now,
    )


def save_document(
    project_path: Path,
    relative_path: str,
    content: str,
    base_hash: str,
    change_source: str,
    label: str | None = None,
) -> DocumentInfo:
    """Save changes to an existing document with optimistic concurrency.

    content is the full file content including frontmatter — what GET returns
    is what PUT accepts, ensuring exact round-trip fidelity. The only mutation
    is updating the 'updated' field in frontmatter.

    base_hash must match the current file's hash, or ConflictError is raised.
    """
    normalized_path = _validate_document_path(relative_path)
    canonical_full = project_path / normalized_path

    if not canonical_full.exists():
        raise FileNotFoundError(f"Document not found: {normalized_path}")

    # Conflict check
    current_bytes = canonical_full.read_bytes()
    current_hash = compute_content_hash(current_bytes)
    if current_hash != base_hash:
        raise ConflictError(current_hash, base_hash)

    # Parse the incoming content as a full frontmatter document.
    # This preserves whatever the client sent (including frontmatter).
    post = frontmatter.loads(content)
    post["updated"] = datetime.now(UTC).strftime("%Y-%m-%d")
    new_bytes = frontmatter.dumps(post).encode()

    new_hash = compute_content_hash(new_bytes)
    if new_hash == current_hash:
        # Content unchanged after frontmatter rebuild — return current state
        ver = get_current_version(project_path, normalized_path)
        return _build_doc_info(post, normalized_path, ver)

    # create_version owns the canonical write transaction.
    # It writes: pending_commit -> version file -> canonical file -> final manifest.
    # Do NOT write the canonical file here — that bypasses the pending_commit protocol.
    version_info = create_version(
        project_path=project_path,
        canonical_path=normalized_path,
        content=new_bytes,
        change_source=change_source,
        label=label,
    )
    if version_info is None:
        raise RuntimeError(f"Updated version was not created for {normalized_path}")

    return _build_doc_info(post, normalized_path, version_info)


def get_document(project_path: Path, relative_path: str) -> DocumentInfo | None:
    """Get document info by reading its canonical file and manifest."""
    normalized_path = _validate_document_path(relative_path)
    canonical_full = project_path / normalized_path
    if not canonical_full.exists():
        return None

    try:
        post = frontmatter.loads(canonical_full.read_text())
    except Exception:
        return None

    ver = get_current_version(project_path, normalized_path)
    return _build_doc_info(post, normalized_path, ver)


def list_documents(project_path: Path) -> list[DocumentInfo]:
    """List all documents in a project by scanning docs/ for files with frontmatter."""
    docs_dir = project_path / "docs"
    if not docs_dir.exists():
        return []

    results = []
    for file_path in sorted(docs_dir.rglob("*")):
        if file_path.is_file() and file_path.suffix in (".md", ".sql", ".yaml", ".json", ".toml"):
            relative = str(file_path.relative_to(project_path))
            info = get_document(project_path, relative)
            if info:
                results.append(info)
    return results


def _build_doc_info(
    post: frontmatter.Post, relative_path: str, ver: VersionInfo | None
) -> DocumentInfo:
    return DocumentInfo(
        title=post.get("title", Path(relative_path).stem),
        doc_type=post.get("type", "unknown"),
        status=post.get("status", "draft"),
        tags=post.get("tags", []),
        relative_path=relative_path,
        version=ver.version_number if ver else 0,
        content_hash=ver.content_hash if ver else "",
        document_uid=ver.document_uid if ver else "",
        created=post.get("created"),
        updated=post.get("updated"),
    )
