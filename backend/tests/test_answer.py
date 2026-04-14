from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from datum.services.answer import (
    NO_SOURCES_RESPONSE,
    build_answer_prompt,
    extract_citation_indices,
    generate_answer,
)
from datum.services.model_gateway import ModelConfig, ModelGateway


def test_build_answer_prompt_and_extract_citations():
    prompt = build_answer_prompt(
        "How does auth work?",
        [{"index": 1, "path": "docs/auth.md", "heading": "Overview", "content": "JWT auth"}],
    )
    assert "How does auth work?" in prompt
    assert "[1] docs/auth.md" in prompt
    assert extract_citation_indices("Use JWT auth [2] and rotate [1].") == [1, 2]


@pytest.mark.asyncio
async def test_generate_answer_returns_citations():
    gateway = SimpleNamespace(
        llm=ModelConfig(name="gpt-oss-20b", endpoint="http://llm", protocol="openai"),
        generate=AsyncMock(return_value="Auth uses JWT [1]."),
    )
    result = await generate_answer(
        gateway,
        "How does auth work?",
        [
            SimpleNamespace(
                project_slug="alpha",
                document_path="docs/auth.md",
                heading_path="Overview",
                snippet="JWT auth",
                version_number=3,
                content_hash="sha256:abc",
                document_uid="doc_1",
                chunk_id="chunk_1",
                line_start=10,
                line_end=20,
            )
        ],
    )

    assert result.answer == "Auth uses JWT [1]."
    assert result.model == "gpt-oss-20b"
    assert len(result.citations) == 1


@pytest.mark.asyncio
async def test_generate_answer_handles_empty_results():
    gateway = ModelGateway(
        llm=ModelConfig(name="gpt-oss-20b", endpoint="http://llm", protocol="openai")
    )
    result = await generate_answer(gateway, "query", [])
    assert result.error == NO_SOURCES_RESPONSE
    await gateway.close()
