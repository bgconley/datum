"""LLM answer synthesis from search results with stable citations."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from datum.services.citations import Citation, SourceRef

if TYPE_CHECKING:
    from datum.services.search import SearchResult
else:
    SearchResult = Any

ANSWER_PROMPT_TEMPLATE = """You are a project intelligence assistant.
Answer the user's question using ONLY the provided document sources.
Cite every factual claim using [N] notation that matches the source numbers below.

Question: {query}

Sources:
{sources}

Instructions:
- Answer concisely and accurately using only the provided sources
- Cite factual claims with [N]
- If the sources are insufficient, say you cannot answer from the available project documents
"""

NO_SOURCES_RESPONSE = "No source documents were found for this query."


@dataclass(slots=True)
class AnswerResponse:
    answer: str = ""
    citations: list[Citation] = field(default_factory=list)
    error: str = ""
    model: str = ""


class SearchResultLike(Protocol):
    project_slug: str
    document_path: str
    heading_path: str | None
    snippet: str
    version_number: int
    content_hash: str
    document_uid: str
    chunk_id: str
    line_start: int
    line_end: int


class GatewayLike(Protocol):
    llm: Any

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str: ...


AnswerSearchResult = SearchResultLike | SearchResult


def build_answer_prompt(query: str, sources: list[dict]) -> str:
    if not sources:
        return f"Question: {query}\n\nNo sources available. Say you cannot answer."
    body = "\n\n".join(
        f"[{source['index']}] {source['path']}"
        + (f', section "{source["heading"]}"' if source.get("heading") else "")
        + f"\n{source['content']}"
        for source in sources
    )
    return ANSWER_PROMPT_TEMPLATE.format(query=query, sources=body)


def extract_citation_indices(text: str) -> list[int]:
    matches = re.findall(r"\[(\d+)\]", text)
    return sorted({int(match) for match in matches})


async def generate_answer(
    gateway: GatewayLike, query: str, search_results: Sequence[AnswerSearchResult]
) -> AnswerResponse:
    if not search_results:
        return AnswerResponse(
            error=NO_SOURCES_RESPONSE,
            model=getattr(getattr(gateway, "llm", None), "name", ""),
        )

    numbered_sources: list[dict] = []
    source_map: dict[int, AnswerSearchResult] = {}
    for index, result in enumerate(search_results[:10], start=1):
        numbered_sources.append(
            {
                "index": index,
                "path": result.document_path,
                "heading": result.heading_path,
                "content": result.snippet,
            }
        )
        source_map[index] = result

    prompt = build_answer_prompt(query, numbered_sources)
    try:
        answer = await gateway.generate(prompt)
    except Exception as exc:
        return AnswerResponse(
            error=str(exc),
            model=getattr(getattr(gateway, "llm", None), "name", ""),
        )

    citations: list[Citation] = []
    for index in extract_citation_indices(answer):
        if index not in source_map:
            continue
        result = source_map[index]
        heading_path = []
        if result.heading_path:
            heading_path = [part.strip() for part in result.heading_path.split(">") if part.strip()]
        citations.append(
            Citation(
                index=index,
                human_readable=(
                    f"{result.project_slug}/{result.document_path} v{result.version_number}"
                    + (f', section "{result.heading_path}"' if result.heading_path else "")
                ),
                source_ref=SourceRef(
                    project_slug=result.project_slug,
                    document_uid=result.document_uid,
                    version_number=result.version_number,
                    content_hash=result.content_hash,
                    chunk_id=result.chunk_id,
                    canonical_path=result.document_path,
                    heading_path=heading_path,
                    line_start=result.line_start,
                    line_end=result.line_end,
                ),
            )
        )

    return AnswerResponse(
        answer=answer,
        citations=citations,
        model=getattr(getattr(gateway, "llm", None), "name", ""),
    )
