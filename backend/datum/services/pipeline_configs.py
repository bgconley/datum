"""Stable pipeline configuration and active model-run helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datum.models.core import ModelRun, PipelineConfig
from datum.services.chunking import (
    CHUNKING_PIPELINE_NAME,
    CHUNKING_PIPELINE_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OVERLAP_TOKENS,
    ENCODING,
)
from datum.services.model_gateway import ModelGateway
from datum.services.technical_terms import (
    PATTERNS,
    TECHNICAL_TERMS_PIPELINE_NAME,
    TECHNICAL_TERMS_PIPELINE_VERSION,
)

EXTRACTION_PIPELINE_NAME = "content-extraction-router"
EXTRACTION_PIPELINE_VERSION = "phase2-router-v1"
RETRIEVAL_PIPELINE_NAME = "hybrid-search"
RETRIEVAL_PIPELINE_VERSION = "phase2-rrf-v1"
RETRIEVAL_RRF_K = 60
RETRIEVAL_WEIGHTS = {
    "bm25": 1.0,
    "vector": 1.0,
    "terms": 0.5,
}


def stable_config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_ingestion_job_idempotency_key(
    *,
    project_id: Any,
    version_id: Any,
    job_type: str,
    content_hash: str,
    pipeline_config_hash: str,
    model_run_id: Any | None = None,
) -> str:
    model_part = str(model_run_id) if model_run_id else "none"
    return (
        f"{project_id}:{version_id}:{job_type}:{content_hash}:"
        f"{pipeline_config_hash}:{model_part}"
    )


def extraction_pipeline_payload() -> dict[str, Any]:
    return {
        "version": EXTRACTION_PIPELINE_VERSION,
        "strategy": "filesystem-router",
        "text_kinds": ["raw", "extracted", "unsupported"],
    }


def chunking_pipeline_payload() -> dict[str, Any]:
    return {
        "version": CHUNKING_PIPELINE_VERSION,
        "strategy": "heading_aware",
        "tokenizer": ENCODING.name,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "overlap_tokens": DEFAULT_OVERLAP_TOKENS,
    }


def technical_terms_pipeline_payload() -> dict[str, Any]:
    return {
        "version": TECHNICAL_TERMS_PIPELINE_VERSION,
        "strategy": "regex",
        "pattern_types": [name for name, _, _ in PATTERNS],
    }


def retrieval_pipeline_payload() -> dict[str, Any]:
    return {
        "version": RETRIEVAL_PIPELINE_VERSION,
        "strategy": "hybrid_rrf",
        "rrf_k": RETRIEVAL_RRF_K,
        "weights": RETRIEVAL_WEIGHTS,
        "signals": ["bm25", "vector", "technical_terms"],
    }


def embedding_model_payload(gateway: ModelGateway) -> dict[str, Any] | None:
    config = gateway.embedding
    if config is None:
        return None
    return {
        "model_name": config.name,
        "endpoint": config.endpoint,
        "protocol": config.protocol,
        "dimensions": config.dimensions,
        "batch_size": config.batch_size,
    }


def reranker_model_payload(gateway: ModelGateway) -> dict[str, Any] | None:
    config = gateway.reranker
    if config is None:
        return None
    return {
        "model_name": config.name,
        "endpoint": config.endpoint,
        "protocol": config.protocol,
    }


async def get_or_create_pipeline_config(
    session: AsyncSession,
    *,
    stage: str,
    name: str,
    config: dict[str, Any],
) -> PipelineConfig:
    config_hash = stable_config_hash(config)
    result = await session.execute(
        select(PipelineConfig).where(
            PipelineConfig.stage == stage,
            PipelineConfig.config_hash == config_hash,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    pipeline_config = PipelineConfig(
        stage=stage,
        name=name,
        config_hash=config_hash,
        config=config,
    )
    session.add(pipeline_config)
    await session.flush()
    return pipeline_config


async def get_extraction_pipeline_config(session: AsyncSession) -> PipelineConfig:
    return await get_or_create_pipeline_config(
        session,
        stage="extract",
        name=EXTRACTION_PIPELINE_NAME,
        config=extraction_pipeline_payload(),
    )


async def get_chunking_pipeline_config(session: AsyncSession) -> PipelineConfig:
    return await get_or_create_pipeline_config(
        session,
        stage="chunk",
        name=CHUNKING_PIPELINE_NAME,
        config=chunking_pipeline_payload(),
    )


async def get_technical_terms_pipeline_config(session: AsyncSession) -> PipelineConfig:
    return await get_or_create_pipeline_config(
        session,
        stage="technical_terms",
        name=TECHNICAL_TERMS_PIPELINE_NAME,
        config=technical_terms_pipeline_payload(),
    )


async def get_retrieval_pipeline_config(session: AsyncSession) -> PipelineConfig:
    return await get_or_create_pipeline_config(
        session,
        stage="retrieval",
        name=RETRIEVAL_PIPELINE_NAME,
        config=retrieval_pipeline_payload(),
    )


async def get_embedding_pipeline_config(
    session: AsyncSession,
    gateway: ModelGateway,
) -> PipelineConfig | None:
    payload = embedding_model_payload(gateway)
    if payload is None:
        return None
    return await get_or_create_pipeline_config(
        session,
        stage="embed",
        name="embedding-model",
        config=payload,
    )


async def get_active_embedding_model_run(
    session: AsyncSession,
    gateway: ModelGateway,
    *,
    create: bool,
) -> ModelRun | None:
    payload = embedding_model_payload(gateway)
    if payload is None:
        return None

    config_hash = stable_config_hash(payload)
    result = await session.execute(
        select(ModelRun)
        .where(
            ModelRun.task == "embedding",
            ModelRun.model_name == payload["model_name"],
            ModelRun.model_version == config_hash,
        )
        .order_by(ModelRun.started_at.desc().nullslast())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None or not create:
        return existing

    model_run = ModelRun(
        model_name=payload["model_name"],
        model_version=config_hash,
        task="embedding",
        config=payload,
        started_at=datetime.now(UTC),
    )
    session.add(model_run)
    await session.flush()
    return model_run


async def get_active_reranker_model_run(
    session: AsyncSession,
    gateway: ModelGateway,
    *,
    create: bool,
) -> ModelRun | None:
    payload = reranker_model_payload(gateway)
    if payload is None:
        return None

    config_hash = stable_config_hash(payload)
    result = await session.execute(
        select(ModelRun)
        .where(
            ModelRun.task == "reranker",
            ModelRun.model_name == payload["model_name"],
            ModelRun.model_version == config_hash,
        )
        .order_by(ModelRun.started_at.desc().nullslast())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None or not create:
        return existing

    model_run = ModelRun(
        model_name=payload["model_name"],
        model_version=config_hash,
        task="reranker",
        config=payload,
        started_at=datetime.now(UTC),
    )
    session.add(model_run)
    await session.flush()
    return model_run
