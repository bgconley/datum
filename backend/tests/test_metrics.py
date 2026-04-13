from datum.services.metrics import compute_eval_metrics, mrr, ndcg_at_k, recall_at_k


def test_ndcg_at_k_perfect_ranking():
    assert ndcg_at_k(["a", "b"], ["a", "b", "c"], k=5) == 1.0


def test_ndcg_at_k_no_hits():
    assert ndcg_at_k(["a"], ["x", "y"], k=5) == 0.0


def test_recall_at_k_partial():
    assert recall_at_k(["a", "b"], ["a", "x"], k=2) == 0.5


def test_mrr_uses_first_relevant_rank():
    assert mrr(["a", "b"], ["x", "b", "a"]) == 0.5


def test_compute_eval_metrics_aggregates_queries():
    result = compute_eval_metrics(
        [
            {
                "query": "q1",
                "expected_docs": ["a", "b"],
                "actual_docs": ["a", "b"],
                "latency_ms": 100,
            },
            {
                "query": "q2",
                "expected_docs": ["x"],
                "actual_docs": ["z", "x"],
                "latency_ms": 200,
            },
        ],
        k_values=[5, 10],
    )
    assert result["ndcg_at_5"] > 0
    assert result["recall_at_5"] > 0
    assert result["mrr"] > 0
    assert result["mean_latency_ms"] == 150.0
    assert len(result["per_query"]) == 2
