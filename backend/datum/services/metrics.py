"""Information retrieval metrics for evaluation runs."""

from __future__ import annotations

from collections.abc import Sequence
from math import log2
from typing import Any


def ndcg_at_k(expected: Sequence[str], actual: Sequence[str], k: int) -> float:
    if k <= 0 or not expected or not actual:
        return 0.0

    expected_set = set(expected)
    dcg = 0.0
    seen: set[str] = set()
    for index, item in enumerate(actual[:k], start=1):
        if item in expected_set and item not in seen:
            dcg += 1.0 / log2(index + 1)
            seen.add(item)

    ideal_hits = min(len(expected_set), k)
    if ideal_hits == 0:
        return 0.0

    idcg = sum(1.0 / log2(index + 1) for index in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return round(dcg / idcg, 6)


def recall_at_k(expected: Sequence[str], actual: Sequence[str], k: int) -> float:
    if k <= 0 or not expected:
        return 0.0
    expected_set = set(expected)
    if not expected_set:
        return 0.0
    found = expected_set.intersection(actual[:k])
    return round(len(found) / len(expected_set), 6)


def mrr(expected: Sequence[str], actual: Sequence[str]) -> float:
    if not expected or not actual:
        return 0.0
    expected_set = set(expected)
    for index, item in enumerate(actual, start=1):
        if item in expected_set:
            return round(1.0 / index, 6)
    return 0.0


def compute_eval_metrics(
    query_results: Sequence[dict[str, Any]],
    k_values: Sequence[int],
) -> dict[str, Any]:
    k_values = sorted({k for k in k_values if k > 0})
    if not k_values:
        k_values = [5, 10]

    metric_sums: dict[str, float] = {f"ndcg_at_{k}": 0.0 for k in k_values}
    metric_sums.update({f"recall_at_{k}": 0.0 for k in k_values})
    metric_sums["mrr"] = 0.0
    latency_sum = 0.0
    per_query: list[dict[str, Any]] = []

    for query_result in query_results:
        expected = list(query_result.get("expected_docs", []))
        actual = list(query_result.get("actual_docs", []))
        latency_ms = float(query_result.get("latency_ms", 0))

        entry: dict[str, Any] = dict(query_result)
        entry.update(
            {
                "query": query_result.get("query", ""),
                "expected_docs": expected,
                "actual_docs": actual,
                "latency_ms": latency_ms,
            }
        )

        for k in k_values:
            ndcg_key = f"ndcg_at_{k}"
            recall_key = f"recall_at_{k}"
            entry[ndcg_key] = ndcg_at_k(expected, actual, k=k)
            entry[recall_key] = recall_at_k(expected, actual, k=k)
            metric_sums[ndcg_key] += entry[ndcg_key]
            metric_sums[recall_key] += entry[recall_key]

        entry["mrr"] = mrr(expected, actual)
        metric_sums["mrr"] += entry["mrr"]
        latency_sum += latency_ms
        per_query.append(entry)

    count = len(query_results)
    if count == 0:
        return {
            **{key: 0.0 for key in metric_sums},
            "mean_latency_ms": 0.0,
            "per_query": [],
        }

    return {
        **{key: round(value / count, 6) for key, value in metric_sums.items()},
        "mean_latency_ms": round(latency_sum / count, 2),
        "per_query": per_query,
    }
