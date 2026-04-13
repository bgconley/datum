"""Datum evaluation CLI for evaluation and re-embedding workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from datum.db import async_session_factory
from datum.models.evaluation import EvaluationRun, EvaluationSet
from datum.services.evaluation import EvalConfig, compare_runs, run_evaluation
from datum.services.model_gateway import build_model_gateway
from datum.services.reembedding import (
    drop_embeddings,
    get_embedding_stats,
    plan_reembedding,
    start_reembedding,
)

logger = logging.getLogger(__name__)


async def cmd_create_set(args: argparse.Namespace) -> None:
    queries = json.loads(Path(args.queries_file).read_text())
    async with async_session_factory() as session:
        eval_set = EvaluationSet(name=args.name, description=args.description, queries=queries)
        session.add(eval_set)
        await session.commit()
        await session.refresh(eval_set)
        print(f"Created evaluation set: {eval_set.id}")
        print(f"  Name: {eval_set.name}")
        print(f"  Queries: {len(eval_set.queries)}")


async def cmd_run(args: argparse.Namespace) -> None:
    gateway = build_model_gateway()
    try:
        config = EvalConfig(
            retrieval_config_id=(
                UUID(args.retrieval_config_id)
                if args.retrieval_config_id
                else None
            ),
            embedding_model=args.embedding_model,
            embedding_model_run_id=UUID(args.embedding_model_run_id)
            if args.embedding_model_run_id
            else None,
            reranker_model=args.reranker_model,
            reranker_model_run_id=UUID(args.reranker_model_run_id)
            if args.reranker_model_run_id
            else None,
            reranker_enabled=not args.disable_reranker,
            version_scope=args.version_scope,
        )
        async with async_session_factory() as session:
            _, metrics = await run_evaluation(
                session=session,
                eval_set_id=UUID(args.eval_set_id),
                config=config,
                run_name=args.name,
                gateway=gateway if (gateway.embedding or gateway.reranker) else None,
            )
    finally:
        await gateway.close()

    print(f"Evaluation run: {args.name}")
    print(f"  nDCG@5: {metrics.get('ndcg_at_5', 0):.4f}")
    print(f"  nDCG@10: {metrics.get('ndcg_at_10', 0):.4f}")
    print(f"  Recall@5: {metrics.get('recall_at_5', 0):.4f}")
    print(f"  Recall@10: {metrics.get('recall_at_10', 0):.4f}")
    print(f"  MRR: {metrics.get('mrr', 0):.4f}")
    print(f"  Mean latency: {metrics.get('mean_latency_ms', 0):.2f}ms")


async def cmd_compare(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        run_a = await session.get(EvaluationRun, UUID(args.run_a_id))
        run_b = await session.get(EvaluationRun, UUID(args.run_b_id))
        if run_a is None or run_b is None:
            print("ERROR: one or both runs not found", file=sys.stderr)
            raise SystemExit(1)

    comparison = compare_runs(
        {"name": run_a.name, "results": run_a.results},
        {"name": run_b.name, "results": run_b.results},
    )
    print(f"Comparison: {comparison['run_a']} vs {comparison['run_b']}")
    print(f"  Winner: {comparison['winner']}")
    print(
        f"  nDCG@5: {comparison['ndcg_at_5_a']:.4f} vs {comparison['ndcg_at_5_b']:.4f} "
        f"(delta {comparison['ndcg_at_5_delta']:+.4f})"
    )
    print(
        f"  Latency: {comparison['latency_a_ms']:.1f}ms vs {comparison['latency_b_ms']:.1f}ms "
        f"(delta {comparison['latency_delta_ms']:+.1f}ms)"
    )


async def cmd_list_sets(_: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(EvaluationSet).order_by(EvaluationSet.created_at.desc())
        )
        for eval_set in result.scalars().all():
            print(f"{eval_set.id}  {eval_set.name}  ({len(eval_set.queries)} queries)")


async def cmd_list_runs(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        query = select(EvaluationRun).order_by(EvaluationRun.created_at.desc())
        if args.eval_set:
            query = query.where(EvaluationRun.evaluation_set_id == UUID(args.eval_set))
        result = await session.execute(query)
        for run in result.scalars().all():
            print(
                f"{run.id}  {run.name}  "
                f"nDCG@5={float(run.results.get('ndcg_at_5', 0)):.4f}"
            )


async def cmd_stats(_: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        stats = await get_embedding_stats(session)
    for item in stats:
        print(
            f"{item['model_name']}  run={item['model_run_id']}  "
            f"count={item['embedding_count']}"
        )


async def cmd_reembed(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        plan = await plan_reembedding(session, args.model, batch_size=args.batch_size)
        print(f"Re-embedding plan for {args.model}: {plan.total_chunks} chunks")
        if plan.total_chunks == 0:
            return
        run_id = await start_reembedding(
            session,
            model_name=args.model,
            model_version=args.version,
            dimensions=args.dimensions,
            batch_size=args.batch_size,
        )
        print(f"Queued re-embedding run: {run_id}")


async def cmd_drop(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        deleted = await drop_embeddings(session, UUID(args.model_run_id))
    print(f"Dropped {deleted} embeddings")


def build_parser(prog: str = "datum-eval") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="Datum evaluation harness")
    subparsers = parser.add_subparsers(dest="command")

    p_create = subparsers.add_parser("create-set")
    p_create.add_argument("name")
    p_create.add_argument("queries_file")
    p_create.add_argument("--description", default=None)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("eval_set_id")
    p_run.add_argument("--name", required=True)
    p_run.add_argument("--retrieval-config-id", default=None)
    p_run.add_argument("--embedding-model", default=None)
    p_run.add_argument("--embedding-model-run-id", default=None)
    p_run.add_argument("--reranker-model", default=None)
    p_run.add_argument("--reranker-model-run-id", default=None)
    p_run.add_argument("--disable-reranker", action="store_true")
    p_run.add_argument("--version-scope", default="current")

    p_compare = subparsers.add_parser("compare")
    p_compare.add_argument("run_a_id")
    p_compare.add_argument("run_b_id")

    subparsers.add_parser("list-sets")

    p_list_runs = subparsers.add_parser("list-runs")
    p_list_runs.add_argument("--eval-set", default=None)

    subparsers.add_parser("stats")

    p_reembed = subparsers.add_parser("reembed")
    p_reembed.add_argument("--model", required=True)
    p_reembed.add_argument("--version", default=None)
    p_reembed.add_argument("--dimensions", type=int, default=1024)
    p_reembed.add_argument("--batch-size", type=int, default=64)

    p_drop = subparsers.add_parser("drop-embeddings")
    p_drop.add_argument("model_run_id")

    return parser


async def _dispatch(args: argparse.Namespace) -> None:
    commands = {
        "create-set": cmd_create_set,
        "run": cmd_run,
        "compare": cmd_compare,
        "list-sets": cmd_list_sets,
        "list-runs": cmd_list_runs,
        "stats": cmd_stats,
        "reembed": cmd_reembed,
        "drop-embeddings": cmd_drop,
    }
    handler = commands.get(args.command)
    if handler is None:
        raise SystemExit(2)
    await handler(args)


def main(argv: Sequence[str] | None = None, *, prog: str = "datum-eval") -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser(prog=prog)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.command:
        parser.print_help()
        return
    asyncio.run(_dispatch(args))


if __name__ == "__main__":
    main()
