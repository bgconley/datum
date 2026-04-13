"""Evaluation harness for search quality comparisons."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.evaluation import EvaluationRun, EvaluationSet
from datum.services.metrics import compute_eval_metrics
from datum.services.model_gateway import ModelGateway
from datum.services.pipeline_configs import (
    get_active_embedding_model_run,
    get_active_reranker_model_run,
)
from datum.services.search import SearchOptions, SearchResult, search

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EvalConfig:
    retrieval_config_id: UUID | None = None
    embedding_model: str | None = None
    embedding_model_run_id: UUID | None = None
    reranker_model: str | None = None
    reranker_model_run_id: UUID | None = None
    reranker_enabled: bool = True
    version_scope: str = "current"
    chunking_config: dict[str, Any] | None = None
    fusion_weights: dict[str, Any] | None = None

    def to_search_options(self) -> SearchOptions:
        return SearchOptions(
            retrieval_config_id=self.retrieval_config_id,
            embedding_model_run_id=self.embedding_model_run_id,
            reranker_enabled=self.reranker_enabled,
            reranker_model_run_id=self.reranker_model_run_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_config_id": (
                str(self.retrieval_config_id)
                if self.retrieval_config_id
                else None
            ),
            "embedding_model": self.embedding_model,
            "embedding_model_run_id": (
                str(self.embedding_model_run_id) if self.embedding_model_run_id else None
            ),
            "reranker_model": self.reranker_model,
            "reranker_model_run_id": (
                str(self.reranker_model_run_id) if self.reranker_model_run_id else None
            ),
            "reranker_enabled": self.reranker_enabled,
            "version_scope": self.version_scope,
            "chunking_config": self.chunking_config,
            "fusion_weights": self.fusion_weights,
        }


def create_evaluation_set(
    name: str,
    queries: list[dict[str, Any]],
    description: str | None = None,
) -> dict[str, Any]:
    return {"name": name, "description": description, "queries": queries}


def _expected_identifier(expectation: dict[str, Any]) -> str:
    heading = expectation.get("heading_path_contains")
    if heading:
        return f"{expectation['doc_path']}#{str(heading).strip().lower()}"
    return str(expectation["doc_path"])


def _matches_expectation(result: SearchResult, expectation: dict[str, Any]) -> bool:
    if result.document_path != expectation.get("doc_path"):
        return False
    heading_contains = expectation.get("heading_path_contains")
    if heading_contains:
        return str(heading_contains).lower() in result.heading_path.lower()
    return True


def _match_expected_results(
    expected_results: list[dict[str, Any]],
    actual_results: list[SearchResult],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    expected_ids = [_expected_identifier(expectation) for expectation in expected_results]
    matched_actual_ids: list[str] = []
    per_expectation: list[dict[str, Any]] = []
    used_indices: set[int] = set()

    for expectation in expected_results:
        actual_rank: int | None = None
        for index, result in enumerate(actual_results, start=1):
            if index in used_indices:
                continue
            if _matches_expectation(result, expectation):
                actual_rank = index
                used_indices.add(index)
                matched_actual_ids.append(_expected_identifier(expectation))
                break

        rank_threshold = expectation.get("rank_threshold")
        per_expectation.append(
            {
                **expectation,
                "actual_rank": actual_rank,
                "threshold_met": (
                    actual_rank is not None
                    and rank_threshold is not None
                    and actual_rank <= rank_threshold
                )
                if rank_threshold is not None
                else actual_rank is not None,
            }
        )

    return expected_ids, matched_actual_ids, per_expectation


def _build_effective_gateway(
    base_gateway: ModelGateway | None,
    config: EvalConfig,
) -> ModelGateway | None:
    if base_gateway is None:
        return None

    embedding = base_gateway.embedding
    reranker = base_gateway.reranker

    if embedding is None and config.embedding_model is not None:
        raise ValueError("embedding model override requires an embedding gateway")
    if reranker is None and config.reranker_model is not None:
        raise ValueError("reranker model override requires a reranker gateway")

    if embedding is not None and config.embedding_model:
        embedding = replace(embedding, name=config.embedding_model)
    if config.reranker_enabled:
        if reranker is not None and config.reranker_model:
            reranker = replace(reranker, name=config.reranker_model)
    else:
        reranker = None

    if embedding is base_gateway.embedding and reranker is base_gateway.reranker:
        return base_gateway
    return ModelGateway(embedding=embedding, reranker=reranker)


async def _resolve_effective_eval_config(
    session: AsyncSession,
    gateway: ModelGateway | None,
    config: EvalConfig,
) -> EvalConfig:
    resolved = replace(config)

    if gateway and gateway.embedding and resolved.embedding_model is None:
        resolved.embedding_model = gateway.embedding.name
    if (
        gateway
        and gateway.embedding
        and resolved.embedding_model_run_id is None
    ):
        embedding_run = await get_active_embedding_model_run(session, gateway, create=False)
        if embedding_run is not None:
            resolved.embedding_model_run_id = embedding_run.id

    if not resolved.reranker_enabled or not gateway or not gateway.reranker:
        resolved.reranker_model = None if not resolved.reranker_enabled else resolved.reranker_model
        resolved.reranker_model_run_id = None
        return resolved

    if resolved.reranker_model is None:
        resolved.reranker_model = gateway.reranker.name
    if resolved.reranker_model_run_id is None:
        reranker_run = await get_active_reranker_model_run(session, gateway, create=True)
        if reranker_run is not None:
            resolved.reranker_model_run_id = reranker_run.id

    return resolved


async def run_evaluation(
    session: AsyncSession,
    eval_set_id: UUID,
    config: EvalConfig,
    run_name: str,
    gateway: ModelGateway | None = None,
    k_values: list[int] | None = None,
) -> tuple[EvaluationRun, dict[str, Any]]:
    if k_values is None:
        k_values = [5, 10]

    eval_set = await session.get(EvaluationSet, eval_set_id)
    if eval_set is None:
        raise ValueError(f"evaluation set {eval_set_id} not found")

    effective_gateway = _build_effective_gateway(gateway, config)
    owns_gateway = effective_gateway is not None and effective_gateway is not gateway
    effective_config = await _resolve_effective_eval_config(session, effective_gateway, config)

    try:
        query_results: list[dict[str, Any]] = []
        for gold_query in eval_set.queries:
            query_text = str(gold_query["query"])
            expected_results = list(gold_query.get("expected_results", []))

            started = time.monotonic()
            try:
                results = await search(
                    session=session,
                    query=query_text,
                    gateway=effective_gateway,
                    version_scope=effective_config.version_scope,
                    limit=max(k_values),
                    search_options=effective_config.to_search_options(),
                )
            except Exception as exc:
                logger.warning("evaluation query failed for %s: %s", query_text, exc)
                results = []
            latency_ms = int((time.monotonic() - started) * 1000)

            expected_ids, matched_ids, per_expectation = _match_expected_results(
                expected_results,
                results,
            )
            actual_results = [
                {
                    "doc_path": result.document_path,
                    "heading_path": result.heading_path,
                    "rank": index + 1,
                }
                for index, result in enumerate(results)
            ]
            query_results.append(
                {
                    "query": query_text,
                    "expected_docs": expected_ids,
                    "actual_docs": matched_ids,
                    "expected_results": expected_results,
                    "actual_results": actual_results,
                    "matches": per_expectation,
                    "latency_ms": latency_ms,
                }
            )

        metrics = compute_eval_metrics(query_results, k_values=k_values)
        eval_run = EvaluationRun(
            evaluation_set_id=eval_set_id,
            name=run_name,
            retrieval_config_id=effective_config.retrieval_config_id,
            embedding_model=effective_config.embedding_model,
            embedding_model_run_id=effective_config.embedding_model_run_id,
            reranker_model=effective_config.reranker_model,
            reranker_model_run_id=effective_config.reranker_model_run_id,
            version_scope=effective_config.version_scope,
            chunking_config=effective_config.chunking_config,
            fusion_weights=effective_config.fusion_weights,
            search_overrides=effective_config.to_dict(),
            results=metrics,
        )
        session.add(eval_run)
        await session.commit()
        await session.refresh(eval_run)
        return eval_run, metrics
    finally:
        if owns_gateway and effective_gateway is not None:
            await effective_gateway.close()


def compare_runs(run_a: dict[str, Any], run_b: dict[str, Any]) -> dict[str, Any]:
    a = dict(run_a.get("results", {}))
    b = dict(run_b.get("results", {}))

    ndcg_a = float(a.get("ndcg_at_5", 0.0))
    ndcg_b = float(b.get("ndcg_at_5", 0.0))
    recall_a = float(a.get("recall_at_5", 0.0))
    recall_b = float(b.get("recall_at_5", 0.0))
    mrr_a = float(a.get("mrr", 0.0))
    mrr_b = float(b.get("mrr", 0.0))
    latency_a = float(a.get("mean_latency_ms", 0.0))
    latency_b = float(b.get("mean_latency_ms", 0.0))

    if ndcg_a > ndcg_b + 0.01:
        winner = run_a["name"]
    elif ndcg_b > ndcg_a + 0.01:
        winner = run_b["name"]
    elif recall_a > recall_b + 0.01:
        winner = run_a["name"]
    elif recall_b > recall_a + 0.01:
        winner = run_b["name"]
    elif mrr_a > mrr_b + 0.01:
        winner = run_a["name"]
    elif mrr_b > mrr_a + 0.01:
        winner = run_b["name"]
    else:
        winner = "tie"

    return {
        "winner": winner,
        "run_a": run_a["name"],
        "run_b": run_b["name"],
        "ndcg_at_5_a": ndcg_a,
        "ndcg_at_5_b": ndcg_b,
        "ndcg_at_5_delta": round(ndcg_b - ndcg_a, 4),
        "recall_at_5_a": recall_a,
        "recall_at_5_b": recall_b,
        "mrr_a": mrr_a,
        "mrr_b": mrr_b,
        "latency_a_ms": latency_a,
        "latency_b_ms": latency_b,
        "latency_delta_ms": round(latency_b - latency_a, 1),
    }
