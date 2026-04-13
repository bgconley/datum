from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.db import get_session
from datum.models.evaluation import EvaluationRun, EvaluationSet
from datum.schemas.evaluation import (
    CompareResponse,
    EmbeddingStatsResponse,
    EvalRunRequest,
    EvalRunResponse,
    EvalSetCreate,
    EvalSetResponse,
)
from datum.services.evaluation import EvalConfig, compare_runs, run_evaluation
from datum.services.model_gateway import build_model_gateway
from datum.services.reembedding import get_embedding_stats

router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])


@router.post("/sets", response_model=EvalSetResponse, status_code=201)
async def api_create_eval_set(
    body: EvalSetCreate,
    session: AsyncSession = Depends(get_session),
):
    eval_set = EvaluationSet(name=body.name, description=body.description, queries=body.queries)
    session.add(eval_set)
    await session.commit()
    await session.refresh(eval_set)
    return EvalSetResponse(
        id=str(eval_set.id),
        name=eval_set.name,
        description=eval_set.description,
        query_count=len(eval_set.queries),
        created_at=eval_set.created_at.isoformat() if eval_set.created_at is not None else None,
    )


@router.get("/sets", response_model=list[EvalSetResponse])
async def api_list_eval_sets(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(EvaluationSet).order_by(EvaluationSet.created_at.desc().nullslast())
    )
    sets = result.scalars().all()
    return [
        EvalSetResponse(
            id=str(item.id),
            name=item.name,
            description=item.description,
            query_count=len(item.queries),
            created_at=item.created_at.isoformat() if item.created_at is not None else None,
        )
        for item in sets
    ]


@router.post("/runs", response_model=EvalRunResponse, status_code=201)
async def api_run_evaluation(
    body: EvalRunRequest,
    session: AsyncSession = Depends(get_session),
):
    gateway = build_model_gateway()
    try:
        eval_run, metrics = await run_evaluation(
            session=session,
            eval_set_id=UUID(body.eval_set_id),
            config=EvalConfig(
                retrieval_config_id=UUID(body.retrieval_config_id)
                if body.retrieval_config_id
                else None,
                embedding_model=body.embedding_model,
                embedding_model_run_id=UUID(body.embedding_model_run_id)
                if body.embedding_model_run_id
                else None,
                reranker_model=body.reranker_model,
                reranker_model_run_id=UUID(body.reranker_model_run_id)
                if body.reranker_model_run_id
                else None,
                reranker_enabled=body.reranker_enabled,
                version_scope=body.version_scope,
            ),
            run_name=body.name,
            gateway=gateway if (gateway.embedding or gateway.reranker) else None,
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    finally:
        await gateway.close()

    return EvalRunResponse(
        id=str(eval_run.id),
        name=eval_run.name,
        results=metrics,
        created_at=eval_run.created_at.isoformat() if eval_run.created_at is not None else None,
    )


@router.get("/runs", response_model=list[EvalRunResponse])
async def api_list_eval_runs(
    eval_set: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(EvaluationRun).order_by(EvaluationRun.created_at.desc().nullslast())
    if eval_set:
        query = query.where(EvaluationRun.evaluation_set_id == UUID(eval_set))
    result = await session.execute(query)
    runs = result.scalars().all()
    return [
        EvalRunResponse(
            id=str(item.id),
            name=item.name,
            results=item.results,
            created_at=item.created_at.isoformat() if item.created_at is not None else None,
        )
        for item in runs
    ]


@router.get("/compare/{run_a_id}/{run_b_id}", response_model=CompareResponse)
async def api_compare_runs(
    run_a_id: str,
    run_b_id: str,
    session: AsyncSession = Depends(get_session),
):
    run_a = await session.get(EvaluationRun, UUID(run_a_id))
    run_b = await session.get(EvaluationRun, UUID(run_b_id))
    if run_a is None or run_b is None:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    return CompareResponse(
        **compare_runs(
            {"name": run_a.name, "results": run_a.results},
            {"name": run_b.name, "results": run_b.results},
        )
    )


@router.get("/stats", response_model=EmbeddingStatsResponse)
async def api_embedding_stats(session: AsyncSession = Depends(get_session)):
    return EmbeddingStatsResponse(models=await get_embedding_stats(session))
