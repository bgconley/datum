from uuid import uuid4

import pytest

from datum.models.evaluation import EvaluationRun, EvaluationSet
from datum.services.evaluation import (
    EvalConfig,
    compare_runs,
    create_evaluation_set,
    run_evaluation,
)
from datum.services.search import SearchResult


class _EvalSession:
    def __init__(self, eval_set: EvaluationSet | None):
        self.eval_set = eval_set
        self.added = []
        self.committed = False
        self.refreshed = []

    async def get(self, model, key):
        if model is EvaluationSet and self.eval_set and self.eval_set.id == key:
            return self.eval_set
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)


def test_create_evaluation_set_payload():
    eval_set = create_evaluation_set(
        "gold",
        [{"query": "DATABASE_URL", "expected_results": [{"doc_path": "docs/a.md"}]}],
        description="test",
    )
    assert eval_set["name"] == "gold"
    assert eval_set["description"] == "test"
    assert len(eval_set["queries"]) == 1


def test_compare_runs_prefers_higher_ndcg():
    comparison = compare_runs(
        {
            "name": "baseline",
            "results": {
                "ndcg_at_5": 0.4,
                "recall_at_5": 0.7,
                "mrr": 0.5,
                "mean_latency_ms": 120,
            },
        },
        {
            "name": "candidate",
            "results": {
                "ndcg_at_5": 0.8,
                "recall_at_5": 0.7,
                "mrr": 0.5,
                "mean_latency_ms": 160,
            },
        },
    )
    assert comparison["winner"] == "candidate"
    assert comparison["ndcg_at_5_delta"] > 0


@pytest.mark.asyncio
async def test_run_evaluation_uses_search_overrides(monkeypatch):
    eval_set_id = uuid4()
    session = _EvalSession(
        EvaluationSet(
            id=eval_set_id,
            name="gold",
            description=None,
            queries=[
                {
                    "query": "DATABASE_URL",
                    "expected_results": [
                        {
                            "doc_path": "docs/search.md",
                            "heading_path_contains": "Intro",
                            "rank_threshold": 1,
                        }
                    ],
                }
            ],
        )
    )
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return [
            SearchResult(
                document_title="Search Doc",
                document_path="docs/search.md",
                project_slug="p",
                heading_path="Intro",
                snippet="Use DATABASE_URL",
                version_number=1,
                content_hash="sha256:abc",
                fused_score=1.0,
                matched_terms=["DATABASE_URL"],
            )
        ]

    monkeypatch.setattr("datum.services.evaluation.search", fake_search)

    eval_run, metrics = await run_evaluation(
        session=session,
        eval_set_id=eval_set_id,
        config=EvalConfig(
            retrieval_config_id=uuid4(),
            embedding_model_run_id=uuid4(),
            reranker_enabled=False,
            version_scope="all",
        ),
        run_name="baseline",
        gateway=None,
    )

    assert captured["version_scope"] == "all"
    assert captured["search_options"].embedding_model_run_id is not None
    assert captured["search_options"].reranker_enabled is False
    assert metrics["ndcg_at_5"] > 0
    assert isinstance(eval_run, EvaluationRun)
    assert session.committed is True
