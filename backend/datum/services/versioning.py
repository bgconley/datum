"""Version creation following the design doc's atomic write protocol.

Write order (design doc Section 5, Write Path 1, step 3):
  a. Write temp file
  b. fsync temp
  c. Determine next version
  d. Write manifest with pending_commit
  e. fsync manifest dir
  f. Copy temp to version path
  g. fsync version file
  h. Rename temp over canonical (if needed)
  i. fsync canonical dir
  j. Write final manifest (remove pending_commit, advance head)
  k. fsync manifest dir
"""
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone


class StalePendingCommitError(Exception):
    """Raised when a stale pending_commit with an existing version file blocks versioning.

    The reconciler must resolve this state before new versions can be created.
    """
    def __init__(self, canonical_path: str, version: int, version_file: str):
        self.canonical_path = canonical_path
        self.version = version
        self.version_file = version_file
        super().__init__(
            f"Stale pending_commit for version {version} with existing "
            f"version file at {version_file}. Run reconciler to recover."
        )
from pathlib import Path
from typing import Optional

from datum.services.filesystem import (
    atomic_write,
    compute_content_hash,
    doc_manifest_dir,
    generate_uid,
    read_manifest,
    resolve_manifest_dir,
    write_manifest,
)


@dataclass
class VersionInfo:
    version_number: int
    branch: str
    content_hash: str
    version_file: str
    document_uid: str
    created_at: datetime


def create_version(
    project_path: Path,
    canonical_path: str,
    content: bytes,
    change_source: str,
    branch: str = "main",
    label: Optional[str] = None,
    restored_from: Optional[int] = None,
) -> Optional[VersionInfo]:
    """Create a new immutable version of a document.

    Returns VersionInfo if a new version was created, None if content
    is identical to the current head (idempotent skip).
    """
    content_hash = compute_content_hash(content)
    manifest_dir = resolve_manifest_dir(project_path, canonical_path, for_write=True)
    manifest_path = manifest_dir / "manifest.yaml"

    # Read current manifest (may not exist for new documents)
    manifest = read_manifest(manifest_path)

    # Initialize manifest for new documents
    if not manifest:
        manifest = {
            "document_uid": generate_uid("doc"),
            "canonical_path": canonical_path,
            "branches": {},
        }

    branch_data = manifest.get("branches", {}).get(branch, {"head": None, "versions": []})

    # Handle stale pending_commit from a prior crash.
    # The reconciler owns full recovery, but we must not silently reuse a version
    # slot that a pending_commit already claimed. If the pending_commit's version
    # file exists on disk, the reconciler should complete it. If it doesn't exist,
    # clear the stale pending_commit so we can proceed.
    if "pending_commit" in manifest:
        stale = manifest["pending_commit"]
        stale_version_path = manifest_dir / stale["file"]
        if stale_version_path.exists():
            # Version file was written before the crash — reconciler must handle this.
            # Refuse to create a new version until reconciler clears pending_commit.
            raise StalePendingCommitError(
                canonical_path=canonical_path,
                version=stale["version"],
                version_file=str(stale_version_path),
            )
        else:
            # No version file — the crash happened before step f. Safe to clear.
            del manifest["pending_commit"]
            write_manifest(manifest_path, manifest)

    # Idempotency check: skip if content hash matches head
    if branch_data["versions"]:
        head_hash = branch_data["versions"][-1].get("content_hash")
        if head_hash == content_hash:
            return None

    # Determine next version number
    next_version = len(branch_data["versions"]) + 1
    version_str = f"v{next_version:03d}"
    version_filename = f"{version_str}{Path(canonical_path).suffix}"
    version_rel_path = f"{branch}/{version_filename}"
    version_abs_path = manifest_dir / branch / version_filename

    now = datetime.now(timezone.utc)

    # Write content to temp file first (steps a-b)
    full_canonical = project_path / canonical_path
    full_canonical.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=full_canonical.parent,
        prefix=f".{full_canonical.name}.",
        suffix=".tmp",
    )
    try:
        os.write(fd, content)
        os.fsync(fd)
        os.close(fd)
        fd = -1
    except BaseException:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    # Step d: Write manifest with pending_commit BEFORE touching canonical content
    pending = {
        "version": next_version,
        "branch": branch,
        "file": version_rel_path,
        "content_hash": content_hash,
        "canonical_path": canonical_path,
        "started": now.isoformat(),
    }
    manifest["pending_commit"] = pending
    write_manifest(manifest_path, manifest)

    # Step f: Copy temp to version path
    version_abs_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tmp_path, version_abs_path)
    _fsync_file(version_abs_path)

    # Step h: Rename temp over canonical path (the atomic commit of content)
    os.rename(tmp_path, full_canonical)
    _fsync_dir(full_canonical.parent)
    tmp_path = None  # Consumed by rename

    # Step j: Write final manifest — remove pending_commit, advance head
    version_entry = {
        "version": next_version,
        "file": version_rel_path,
        "content_hash": content_hash,
        "created": now.isoformat(),
    }
    if label:
        version_entry["label"] = label
    if restored_from is not None:
        version_entry["restored_from"] = restored_from

    branch_data["versions"].append(version_entry)
    branch_data["head"] = version_str
    manifest.setdefault("branches", {})[branch] = branch_data
    del manifest["pending_commit"]
    write_manifest(manifest_path, manifest)

    return VersionInfo(
        version_number=next_version,
        branch=branch,
        content_hash=content_hash,
        version_file=version_rel_path,
        document_uid=manifest["document_uid"],
        created_at=now,
    )


def _fsync_file(path: Path) -> None:
    """fsync a file to ensure durability."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    """fsync a directory to ensure rename durability."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def get_current_version(
    project_path: Path, canonical_path: str, branch: str = "main"
) -> Optional[VersionInfo]:
    """Get the current head version info for a document."""
    manifest_dir = resolve_manifest_dir(project_path, canonical_path, for_write=False)
    manifest = read_manifest(manifest_dir / "manifest.yaml")
    if not manifest:
        return None

    branch_data = manifest.get("branches", {}).get(branch)
    if not branch_data or not branch_data.get("versions"):
        return None

    latest = branch_data["versions"][-1]
    return VersionInfo(
        version_number=latest["version"],
        branch=branch,
        content_hash=latest["content_hash"],
        version_file=latest["file"],
        document_uid=manifest["document_uid"],
        created_at=datetime.fromisoformat(latest["created"]),
    )


def list_versions(
    project_path: Path, canonical_path: str, branch: str = "main"
) -> list[VersionInfo]:
    """List all versions of a document on a branch."""
    manifest_dir = resolve_manifest_dir(project_path, canonical_path, for_write=False)
    manifest = read_manifest(manifest_dir / "manifest.yaml")
    if not manifest:
        return []

    branch_data = manifest.get("branches", {}).get(branch)
    if not branch_data:
        return []

    return [
        VersionInfo(
            version_number=v["version"],
            branch=branch,
            content_hash=v["content_hash"],
            version_file=v["file"],
            document_uid=manifest["document_uid"],
            created_at=datetime.fromisoformat(v["created"]),
        )
        for v in branch_data["versions"]
    ]


def read_version_content(
    project_path: Path, canonical_path: str, version_number: int, branch: str = "main"
) -> Optional[bytes]:
    """Read the content of a specific version."""
    manifest_dir = resolve_manifest_dir(project_path, canonical_path, for_write=False)
    manifest = read_manifest(manifest_dir / "manifest.yaml")
    if not manifest:
        return None

    branch_data = manifest.get("branches", {}).get(branch)
    if not branch_data:
        return None

    for v in branch_data["versions"]:
        if v["version"] == version_number:
            version_path = manifest_dir / v["file"]
            if version_path.exists():
                return version_path.read_bytes()
            return None
    return None
