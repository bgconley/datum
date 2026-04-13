from uuid import uuid4

import pytest

from datum.services.search import FusedResult, _rerank_search_results


class _Gateway:
    reranker = object()

    async def rerank(self, query, documents, top_n=50):
        assert query == "test query"
        assert documents == ["Heading\nlow relevance", "Heading\nhigh relevance"]
        return [(1, 0.95), (0, 0.6)]


@pytest.mark.asyncio
async def test_rerank_search_results_reorders_candidates(monkeypatch):
    async def fake_payloads(session, fused_results):
        return [
            (fused_results[0].chunk_id, "Heading\nlow relevance"),
            (fused_results[1].chunk_id, "Heading\nhigh relevance"),
        ]

    monkeypatch.setattr("datum.services.search._load_chunk_rerank_payloads", fake_payloads)

    reordered, applied = await _rerank_search_results(
        session=object(),
        fused=[
            FusedResult(chunk_id=str(uuid4()), fused_score=0.9),
            FusedResult(chunk_id=str(uuid4()), fused_score=0.8),
        ],
        query="test query",
        gateway=_Gateway(),
        top_n=2,
    )

    assert applied is True
    assert reordered[0].rerank_score == 0.95
    assert reordered[0].fused_score == 0.8
