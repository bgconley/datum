"""Citation building and resolution in dual human/machine format."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class SourceRef:
    project_slug: str
    document_uid: str
    version_number: int
    content_hash: str
    chunk_id: str
    canonical_path: str
    heading_path: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0


@dataclass(slots=True)
class Citation:
    index: int = 0
    human_readable: str = ""
    source_ref: SourceRef | None = None


def build_citation(chunk, version, document, project, *, index: int = 0) -> Citation:
    if isinstance(chunk.heading_path, str):
        heading_path = [part.strip() for part in chunk.heading_path.split(">") if part.strip()]
    else:
        heading_path = [part.strip() for part in (chunk.heading_path or []) if part.strip()]

    human = f"{project.slug}/{document.canonical_path} v{version.version_number}"
    if heading_path:
        human += f', section "{" > ".join(heading_path)}"'

    return Citation(
        index=index,
        human_readable=human,
        source_ref=SourceRef(
            project_slug=project.slug,
            document_uid=document.uid,
            version_number=version.version_number,
            content_hash=version.content_hash,
            chunk_id=str(chunk.id),
            canonical_path=document.canonical_path,
            heading_path=heading_path,
            line_start=getattr(chunk, "start_line", 0) or 0,
            line_end=getattr(chunk, "end_line", 0) or 0,
        ),
    )


def resolve_citation(ref: SourceRef, versions_dir: Path) -> str | None:
    if not versions_dir.exists():
        return None

    search_roots: list[Path] = [versions_dir]
    main_dir = versions_dir / "main"
    if main_dir.exists():
        search_roots.insert(0, main_dir)

    pattern = f"v{ref.version_number:03d}.*"
    matches: list[Path] = []
    for root in search_roots:
        matches.extend(sorted(root.glob(pattern)))
        if matches:
            break

    if not matches:
        return None
    lines = matches[0].read_text().splitlines()
    start = max(ref.line_start - 1, 0)
    end = min(ref.line_end or len(lines), len(lines))
    return "\n".join(lines[start:end])
