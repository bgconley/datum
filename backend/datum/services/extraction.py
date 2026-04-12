"""Text extraction service for Phase 2 ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import frontmatter

from datum.services.filesystem import compute_content_hash

TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".prisma",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(slots=True)
class ExtractionResult:
    content: str
    text_kind: str
    content_hash: str
    source_extension: str


def extract_text(file_path: Path) -> Optional[ExtractionResult]:
    ext = file_path.suffix.lower()

    if ext in TEXT_EXTENSIONS:
        return _extract_text_file(file_path, ext)
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    return _extract_kreuzberg(file_path)


async def extract_text_async(file_path: Path) -> Optional[ExtractionResult]:
    ext = file_path.suffix.lower()

    if ext in TEXT_EXTENSIONS:
        return _extract_text_file(file_path, ext)
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext == ".docx":
        return _extract_docx(file_path)
    return await _extract_kreuzberg_async(file_path)


def _build_result(content: str, text_kind: str, source_extension: str) -> ExtractionResult:
    return ExtractionResult(
        content=content,
        text_kind=text_kind,
        content_hash=compute_content_hash(content.encode("utf-8")),
        source_extension=source_extension,
    )


def _extract_text_file(file_path: Path, ext: str) -> ExtractionResult:
    raw = file_path.read_text(encoding="utf-8", errors="replace")

    if ext == ".md":
        try:
            content = frontmatter.loads(raw).content
        except Exception:
            content = raw
    else:
        content = raw

    return _build_result(content, "raw", ext)


def _extract_pdf(file_path: Path) -> ExtractionResult:
    try:
        import pymupdf4llm

        content = pymupdf4llm.to_markdown(str(file_path))
        if content and content.strip():
            return _build_result(content, "extracted", ".pdf")
    except Exception:
        pass
    return _extract_kreuzberg(file_path)


def _extract_docx(file_path: Path) -> ExtractionResult:
    try:
        import docx

        document = docx.Document(str(file_path))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        if parts:
            return _build_result("\n\n".join(parts), "extracted", ".docx")
    except Exception:
        pass
    return _extract_kreuzberg(file_path)


def _extract_kreuzberg(file_path: Path) -> ExtractionResult:
    try:
        from kreuzberg import extract_file

        result = asyncio.run(extract_file(file_path))
        if result and result.content and result.content.strip():
            return _build_result(result.content, "extracted", file_path.suffix.lower())
    except Exception:
        pass

    return _build_result("", "unsupported", file_path.suffix.lower())


async def _extract_kreuzberg_async(file_path: Path) -> ExtractionResult:
    try:
        from kreuzberg import extract_file

        result = await extract_file(file_path)
        if result and result.content and result.content.strip():
            return _build_result(result.content, "extracted", file_path.suffix.lower())
    except Exception:
        pass

    return _build_result("", "unsupported", file_path.suffix.lower())
