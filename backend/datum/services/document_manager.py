"""Document lifecycle management.

Documents are filesystem-first: the .md/.sql/.yaml file on disk is canonical.
Frontmatter stores human metadata. Hashes and versions live in .piq/ manifests.
"""

import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from datum.services.filesystem import (
    atomic_write,
    compute_content_hash,
    read_manifest,
    resolve_manifest_dir,
    validate_canonical_path,
    write_manifest,
)
from datum.services.versioning import (
    VersionInfo,
    create_version,
    get_current_version,
    read_version_content,
)

# Document paths must live under docs/ per design doc filesystem schema.
# project.yaml, attachments/, and .piq/ have separate semantics.
_ALLOWED_DOC_PREFIXES = ("docs/",)
_TEXT_DOCUMENT_EXTENSIONS = {
    ".md",
    ".sql",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".prisma",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
}
_BINARY_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
}


class ConflictError(Exception):
    """Raised when a save conflicts with the current file state."""

    def __init__(self, current_hash: str, base_hash: str):
        self.current_hash = current_hash
        self.base_hash = base_hash
        super().__init__(
            f"Conflict: file changed (current={current_hash}, base={base_hash})"
        )


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


def _validate_document_folder_path(relative_path: str) -> str:
    """Enforce that folder paths live under docs/ and return the normalized path."""
    resolved = validate_canonical_path(relative_path)
    normalized_path = resolved.as_posix()
    if normalized_path == ".":
        raise ValueError("Folder path must be under docs/, got project root")
    if len(resolved.parts) < 1 or resolved.parts[0] != "docs":
        raise ValueError(f"Folder path must be under docs/, got: {relative_path}")
    return normalized_path


def _deleted_archive_path(project_path: Path, relative_path: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archived = project_path / ".piq" / "deleted" / f"{relative_path}.{timestamp}"
    archived.parent.mkdir(parents=True, exist_ok=True)
    return archived


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


def is_text_document_path(relative_path: str) -> bool:
    return Path(relative_path).suffix.lower() in _TEXT_DOCUMENT_EXTENSIONS


def is_binary_document_path(relative_path: str) -> bool:
    return Path(relative_path).suffix.lower() in _BINARY_DOCUMENT_EXTENSIONS


def _default_doc_type(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix == ".pdf":
        return "reference"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return "image"
    if suffix in {
        ".sql",
        ".prisma",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
    }:
        return "reference"
    return "note"


def _generic_doc_info(relative_path: str, ver: VersionInfo | None) -> DocumentInfo:
    return DocumentInfo(
        title=Path(relative_path).stem.replace("-", " ").replace("_", " ").title(),
        doc_type=_default_doc_type(relative_path),
        status="active",
        tags=[],
        relative_path=relative_path,
        version=ver.version_number if ver else 0,
        content_hash=ver.content_hash if ver else "",
        document_uid=ver.document_uid if ver else "",
        created=None,
        updated=None,
    )


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

    is_frontmatter_document = current_bytes.startswith(b"---\n")
    if is_frontmatter_document:
        # Parse the incoming content as a full frontmatter document.
        # This preserves whatever the client sent (including frontmatter).
        post = frontmatter.loads(content)
        post["updated"] = datetime.now(UTC).strftime("%Y-%m-%d")
        new_bytes = frontmatter.dumps(post).encode()
    else:
        post = None
        new_bytes = content.encode()

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

    if post is not None:
        return _build_doc_info(post, normalized_path, version_info)
    return _generic_doc_info(normalized_path, version_info)


def get_document(project_path: Path, relative_path: str) -> DocumentInfo | None:
    """Get document info by reading its canonical file and manifest."""
    normalized_path = _validate_document_path(relative_path)
    canonical_full = project_path / normalized_path
    if not canonical_full.exists():
        return None

    ver = get_current_version(project_path, normalized_path)
    if is_binary_document_path(normalized_path):
        return _generic_doc_info(normalized_path, ver)

    try:
        text = canonical_full.read_text()
        post = frontmatter.loads(text)
    except Exception:
        if is_text_document_path(normalized_path):
            return _generic_doc_info(normalized_path, ver)
        return None

    if not post.metadata and is_text_document_path(normalized_path):
        return _generic_doc_info(normalized_path, ver)
    return _build_doc_info(post, normalized_path, ver)


def create_document_folder(project_path: Path, relative_path: str) -> str:
    """Create a folder under docs/ and return its normalized relative path."""
    normalized_path = _validate_document_folder_path(relative_path)
    folder_path = project_path / normalized_path
    folder_path.mkdir(parents=True, exist_ok=True)
    return normalized_path


def move_document(
    project_path: Path,
    relative_path: str,
    new_relative_path: str,
) -> DocumentInfo:
    """Move or rename a document and its manifest history to a new docs/ path."""
    normalized_path = _validate_document_path(relative_path)
    normalized_new_path = _validate_document_path(new_relative_path)

    if normalized_path == normalized_new_path:
        info = get_document(project_path, normalized_path)
        if info is None:
            raise FileNotFoundError(f"Document not found: {normalized_path}")
        return info

    source_path = project_path / normalized_path
    destination_path = project_path / normalized_new_path
    if not source_path.exists():
        raise FileNotFoundError(f"Document not found: {normalized_path}")
    if destination_path.exists():
        raise FileExistsError(f"Document already exists: {normalized_new_path}")

    source_manifest_dir = resolve_manifest_dir(
        project_path,
        normalized_path,
        for_write=True,
    )
    destination_manifest_dir = resolve_manifest_dir(
        project_path,
        normalized_new_path,
        for_write=False,
    )
    if (destination_manifest_dir / "manifest.yaml").exists():
        raise FileExistsError(f"Manifest already exists for: {normalized_new_path}")

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_manifest_dir.parent.mkdir(parents=True, exist_ok=True)

    source_bytes = source_path.read_bytes()

    os.rename(source_path, destination_path)
    os.rename(source_manifest_dir, destination_manifest_dir)

    manifest_path = destination_manifest_dir / "manifest.yaml"
    manifest = read_manifest(manifest_path)
    manifest["canonical_path"] = normalized_new_path
    write_manifest(manifest_path, manifest)

    archived_path = _deleted_archive_path(project_path, normalized_path)
    atomic_write(archived_path, source_bytes)

    info = get_document(project_path, normalized_new_path)
    if info is None:
        raise RuntimeError(f"Moved document could not be loaded: {normalized_new_path}")
    return info


def delete_document(project_path: Path, relative_path: str) -> str:
    """Soft-delete a document into .piq/deleted and preserve manifest history."""
    normalized_path = _validate_document_path(relative_path)
    canonical_full = project_path / normalized_path
    if not canonical_full.exists():
        raise FileNotFoundError(f"Document not found: {normalized_path}")

    archived_path = _deleted_archive_path(project_path, normalized_path)
    shutil.move(str(canonical_full), str(archived_path))

    manifest_dir = resolve_manifest_dir(project_path, normalized_path, for_write=False)
    manifest_path = manifest_dir / "manifest.yaml"
    manifest = read_manifest(manifest_path)
    if manifest:
        manifest["deleted_at"] = datetime.now(UTC).isoformat()
        write_manifest(manifest_path, manifest)

    return archived_path.relative_to(project_path).as_posix()


def restore_document_version(
    project_path: Path,
    relative_path: str,
    version_number: int,
    branch: str = "main",
    label: str | None = None,
) -> DocumentInfo:
    """Restore a prior version by creating a new head version from its content."""
    normalized_path = _validate_document_path(relative_path)
    content = read_version_content(
        project_path,
        normalized_path,
        version_number,
        branch=branch,
    )
    if content is None:
        raise FileNotFoundError(
            f"Version {version_number} not found for {normalized_path}"
        )

    next_label = label or f"Restore v{version_number:03d}"
    version_info = create_version(
        project_path=project_path,
        canonical_path=normalized_path,
        content=content,
        change_source="restore",
        branch=branch,
        label=next_label,
        restored_from=version_number,
    )
    if version_info is None:
        info = get_document(project_path, normalized_path)
        if info is None:
            raise FileNotFoundError(f"Document not found: {normalized_path}")
        return info

    restored = get_document(project_path, normalized_path)
    if restored is None:
        raise RuntimeError(f"Restored document could not be loaded: {normalized_path}")
    return restored


def list_documents(project_path: Path) -> list[DocumentInfo]:
    """List all cabinet documents under docs/ that the viewer can open."""
    docs_dir = project_path / "docs"
    if not docs_dir.exists():
        return []

    results = []
    for file_path in sorted(docs_dir.rglob("*")):
        if file_path.is_file() and (
            file_path.suffix.lower() in _TEXT_DOCUMENT_EXTENSIONS
            or file_path.suffix.lower() in _BINARY_DOCUMENT_EXTENSIONS
        ):
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
