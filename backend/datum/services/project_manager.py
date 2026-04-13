"""Project lifecycle management.

Projects are filesystem-first: project.yaml is canonical.
The database mirrors this for search/query.
"""
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from datum.services.filesystem import (
    atomic_write,
    ensure_piq_structure,
    generate_uid,
    write_manifest,
)

# Slug must be a single path component: lowercase alphanumeric, hyphens allowed,
# no slashes, dots, or traversal characters.
_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _validate_slug(slug: str) -> None:
    """Validate that a project slug is a safe single path component."""
    if not slug or not _SLUG_PATTERN.match(slug):
        raise ValueError(
            f"Invalid project slug: '{slug}'. Must be lowercase alphanumeric "
            f"with hyphens, starting with a letter or digit."
        )
    if slug.startswith("-") or slug.endswith("-") or "--" in slug:
        raise ValueError(f"Invalid project slug: '{slug}'. No leading/trailing/double hyphens.")


@dataclass
class ProjectInfo:
    uid: str
    slug: str
    name: str
    description: str | None = None
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    created: str | None = None
    filesystem_path: str | None = None


def create_project(
    projects_root: Path,
    name: str,
    slug: str,
    description: str | None = None,
    tags: list[str] | None = None,
    status: str = "active",
) -> ProjectInfo:
    """Create a new project on disk with canonical directory structure."""
    _validate_slug(slug)
    project_dir = projects_root / slug
    if project_dir.exists():
        raise FileExistsError(f"Project directory already exists: {project_dir}")

    uid = generate_uid("proj")
    now = datetime.now(UTC).isoformat()

    # Create directory structure
    project_dir.mkdir(parents=True)
    for subdir in ["docs", "attachments"]:
        (project_dir / subdir).mkdir()

    # Create .piq structure
    ensure_piq_structure(project_dir)

    # Write project.yaml (canonical metadata)
    project_data: dict[str, object] = {
        "uid": uid,
        "name": name,
        "slug": slug,
        "status": status,
        "created": now,
    }
    if description:
        project_data["description"] = description
    if tags:
        project_data["tags"] = tags

    project_yaml = yaml.dump(project_data, default_flow_style=False, sort_keys=False).encode()
    atomic_write(project_dir / "project.yaml", project_yaml)

    # Version project.yaml using shared helper (hash-checked, gap-safe numbering)
    from datum.services.project_versioning import version_project_yaml
    version_project_yaml(project_dir, content=project_yaml, change_source="create")

    # Write project-level .piq/manifest.yaml
    write_manifest(project_dir / ".piq" / "manifest.yaml", {"documents": []})

    return ProjectInfo(
        uid=uid,
        slug=slug,
        name=name,
        description=description,
        status=status,
        tags=tags or [],
        created=now,
        filesystem_path=str(project_dir),
    )


def list_projects(projects_root: Path) -> list[ProjectInfo]:
    """List all projects by scanning the projects root for project.yaml files."""
    if not projects_root.exists():
        return []
    results = []
    for child in sorted(projects_root.iterdir()):
        if child.is_dir() and (child / "project.yaml").exists():
            info = _read_project_yaml(child)
            if info:
                results.append(info)
    return results


def get_project(projects_root: Path, slug: str) -> ProjectInfo | None:
    """Get a project by slug."""
    _validate_slug(slug)
    project_dir = projects_root / slug
    if not project_dir.exists() or not (project_dir / "project.yaml").exists():
        return None
    return _read_project_yaml(project_dir)


def _read_project_yaml(project_dir: Path) -> ProjectInfo | None:
    """Read project.yaml and return ProjectInfo."""
    try:
        data = yaml.safe_load((project_dir / "project.yaml").read_text())
    except Exception:
        return None
    if not data or not isinstance(data, dict):
        return None
    return ProjectInfo(
        uid=data.get("uid", ""),
        slug=data.get("slug", project_dir.name),
        name=data.get("name", project_dir.name),
        description=data.get("description"),
        status=data.get("status", "active"),
        tags=data.get("tags", []),
        created=data.get("created"),
        filesystem_path=str(project_dir),
    )
