import json
from pathlib import Path
from uuid import uuid4

import pytest

from datum.cli import eval as eval_cli
from datum.cli import main as root_cli
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


def test_sample_eval_set_fixture_exists():
    fixture_path = Path(__file__).parent / "fixtures" / "sample_eval_set.json"
    payload = json.loads(fixture_path.read_text())

    assert len(payload) >= 5
    assert any("DATABASE_URL" in item["query"] for item in payload)
    assert any("/api/v1/users" in item["query"] for item in payload)


def test_eval_parser_supports_root_cli_prog_name():
    parser = eval_cli.build_parser(prog="datum eval")
    assert parser.prog == "datum eval"


def test_root_cli_dispatches_eval_subcommand(monkeypatch):
    captured: dict[str, object] = {}

    def fake_main(argv=None, *, prog="datum-eval"):
        captured["argv"] = argv
        captured["prog"] = prog

    monkeypatch.setattr("datum.cli.eval.main", fake_main)

    root_cli.main(["eval", "stats"])

    assert captured == {"argv": ["stats"], "prog": "datum eval"}


def test_root_cli_help_prints_available_commands(capsys):
    root_cli.main(["--help"])
    output = capsys.readouterr().out

    assert "usage: datum" in output
    assert "{eval}" in output


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
    embedding_run_id = uuid4()
    reranker_run_id = uuid4()
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

    async def fake_embedding_run(session, gateway, create):
        del session, gateway
        assert create is False
        return type("ModelRun", (), {"id": embedding_run_id})()

    async def fake_reranker_run(session, gateway, create):
        del session, gateway
        assert create is True
        return type("ModelRun", (), {"id": reranker_run_id})()

    monkeypatch.setattr(
        "datum.services.evaluation.get_active_embedding_model_run",
        fake_embedding_run,
    )
    monkeypatch.setattr(
        "datum.services.evaluation.get_active_reranker_model_run",
        fake_reranker_run,
    )

    class _Gateway:
        embedding = type("Embedding", (), {"name": "embed-model"})()
        reranker = type("Reranker", (), {"name": "rerank-model"})()

    eval_run, metrics = await run_evaluation(
        session=session,
        eval_set_id=eval_set_id,
        config=EvalConfig(
            retrieval_config_id=uuid4(),
            reranker_enabled=True,
            version_scope="all",
        ),
        run_name="baseline",
        gateway=_Gateway(),
    )

    assert captured["version_scope"] == "all"
    assert captured["search_options"].embedding_model_run_id == embedding_run_id
    assert captured["search_options"].reranker_enabled is True
    assert captured["search_options"].reranker_model_run_id == reranker_run_id
    assert metrics["ndcg_at_5"] > 0
    assert isinstance(eval_run, EvaluationRun)
    assert eval_run.embedding_model == "embed-model"
    assert eval_run.embedding_model_run_id == embedding_run_id
    assert eval_run.reranker_model == "rerank-model"
    assert eval_run.reranker_model_run_id == reranker_run_id
    assert session.committed is True
