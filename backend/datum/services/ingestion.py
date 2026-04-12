"""Phase 2 ingestion pipeline orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from datum.services.chunking import Chunk, chunk_text
from datum.services.extraction import ExtractionResult, extract_text, extract_text_async
from datum.services.technical_terms import TermMatch, extract_technical_terms


@dataclass(slots=True)
class IngestionContext:
    project_path: Path
    canonical_path: str


def run_extraction(ctx: IngestionContext) -> Optional[ExtractionResult]:
    file_path = ctx.project_path / ctx.canonical_path
    if not file_path.exists():
        return None
    return extract_text(file_path)


async def run_extraction_async(ctx: IngestionContext) -> Optional[ExtractionResult]:
    file_path = ctx.project_path / ctx.canonical_path
    if not file_path.exists():
        return None
    return await extract_text_async(file_path)


def run_chunking(text: str, max_tokens: int = 512, overlap_tokens: int = 50) -> list[Chunk]:
    return chunk_text(text, max_tokens=max_tokens, overlap_tokens=overlap_tokens)


def run_technical_terms(text: str) -> list[TermMatch]:
    return extract_technical_terms(text)


async def run_embedding(chunks: list[Chunk], gateway) -> list[list[float]]:
    if not chunks:
        return []
    return await gateway.embed([chunk.content for chunk in chunks])
