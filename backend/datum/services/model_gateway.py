"""Model gateway for embedding and reranking endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Optional

import httpx

from datum.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ModelConfig:
    name: str
    endpoint: str
    protocol: str = "openai"
    dimensions: int = 1024
    batch_size: int = 64
    timeout: float = 30.0


@dataclass(slots=True)
class ModelGateway:
    embedding: Optional[ModelConfig] = None
    reranker: Optional[ModelConfig] = None
    _client: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding:
            raise RuntimeError("No embedding model configured")

        config = self.embedding
        embeddings: list[list[float]] = []

        for start_index in range(0, len(texts), config.batch_size):
            batch = texts[start_index : start_index + config.batch_size]
            started = time.monotonic()

            if config.protocol == "openai":
                response = await self._post(
                    f"{config.endpoint}/v1/embeddings",
                    {"input": batch, "model": config.name},
                )
                data = sorted(response["data"], key=lambda item: item["index"])
                batch_vectors = [item["embedding"][: config.dimensions] for item in data]
            elif config.protocol == "tei":
                response = await self._post(
                    f"{config.endpoint}/embed",
                    {"inputs": batch, "truncate": True},
                )
                batch_vectors = [item[: config.dimensions] for item in response]
            else:
                raise ValueError(f"Unknown protocol: {config.protocol}")

            logger.debug(
                "Embedded batch %s (%s texts) in %.2fs",
                (start_index // config.batch_size) + 1,
                len(batch),
                time.monotonic() - started,
            )
            embeddings.extend(batch_vectors)

        return embeddings

    async def rerank(self, query: str, documents: list[str], top_n: int = 50) -> list[tuple[int, float]]:
        if not self.reranker:
            raise RuntimeError("No reranker model configured")

        config = self.reranker
        if config.protocol == "openai":
            response = await self._post(
                f"{config.endpoint}/v1/rerank",
                {
                    "model": config.name,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                },
            )
            return [(item["index"], item["relevance_score"]) for item in response["results"]]
        if config.protocol == "tei":
            response = await self._post(
                f"{config.endpoint}/rerank",
                {"query": query, "texts": documents, "truncate": True},
            )
            return [(item["index"], item["score"]) for item in response[:top_n]]
        raise ValueError(f"Unknown protocol: {config.protocol}")

    async def check_health(self, model_type: str) -> bool:
        config = getattr(self, model_type, None)
        if not config or not config.endpoint:
            return False
        try:
            await self._get(f"{config.endpoint}/health")
            return True
        except Exception:
            return False

    async def _post(self, url: str, payload: dict) -> dict:
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def _get(self, url: str) -> dict:
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()


def build_model_gateway() -> ModelGateway:
    embedding = None
    if settings.embedding_endpoint:
        embedding = ModelConfig(
            name=settings.embedding_model,
            endpoint=settings.embedding_endpoint,
            protocol=settings.embedding_protocol,
            dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
        )

    reranker = None
    if settings.reranker_endpoint:
        reranker = ModelConfig(
            name=settings.reranker_model,
            endpoint=settings.reranker_endpoint,
            protocol=settings.reranker_protocol,
        )

    return ModelGateway(embedding=embedding, reranker=reranker)
