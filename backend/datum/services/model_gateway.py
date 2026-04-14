"""Model gateway for embedding and reranking endpoints."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from datum.config import settings

logger = logging.getLogger(__name__)


def _score_from_result(item: dict) -> float:
    score = item.get("relevance_score")
    if score is None:
        score = item["score"]
    return float(score)


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
    embedding: ModelConfig | None = None
    reranker: ModelConfig | None = None
    ner: ModelConfig | None = None
    llm: ModelConfig | None = None
    _client: httpx.AsyncClient = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def embed(
        self,
        texts: list[str],
        *,
        input_type: str = "document",
        instruction: str | None = None,
    ) -> list[list[float]]:
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
            elif config.protocol == "qwen3_embedder":
                payload: dict[str, object] = {
                    "input": batch,
                    "model": config.name,
                    "dimensions": config.dimensions,
                    "input_type": input_type,
                }
                if input_type == "query":
                    payload["instruction"] = instruction or settings.embedding_query_instruction
                response = await self._post(f"{config.endpoint}/v1/embeddings", payload)
                data = sorted(response["data"], key=lambda item: item["index"])
                batch_vectors = [item["embedding"] for item in data]
            elif config.protocol == "tei":
                response = await self._post(
                    f"{config.endpoint}/embed",
                    {"inputs": batch, "truncate": True},
                )
                batch_vectors = [item[: config.dimensions] for item in response]
            else:
                raise ValueError(f"Unknown protocol: {config.protocol}")

            for vector in batch_vectors:
                if len(vector) != config.dimensions:
                    raise ValueError(
                        f"embedding response dimensions {len(vector)} do not match configured "
                        f"dimension {config.dimensions}"
                    )

            logger.debug(
                "Embedded batch %s (%s texts) in %.2fs",
                (start_index // config.batch_size) + 1,
                len(batch),
                time.monotonic() - started,
            )
            embeddings.extend(batch_vectors)

        return embeddings

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 50,
    ) -> list[tuple[int, float]]:
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
            return [(item["index"], _score_from_result(item)) for item in response["results"]]
        if config.protocol == "qwen3_reranker":
            response = await self._post(
                f"{config.endpoint}/v1/rerank",
                {
                    "model": config.name,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                    "instruction": settings.reranker_instruction,
                },
            )
            return [(item["index"], _score_from_result(item)) for item in response["results"]]
        if config.protocol == "tei":
            response = await self._post(
                f"{config.endpoint}/rerank",
                {"query": query, "texts": documents, "truncate": True},
            )
            return [(item["index"], item["score"]) for item in response[:top_n]]
        raise ValueError(f"Unknown protocol: {config.protocol}")

    async def extract_entities(
        self,
        text: str,
        *,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, Any]]:
        if not self.ner:
            raise RuntimeError("No NER model configured")

        config = self.ner
        if config.protocol != "gliner_http":
            raise ValueError(f"Unknown protocol: {config.protocol}")

        response = await self._post(
            f"{config.endpoint}/extract",
            {
                "text": text,
                "labels": labels,
                "threshold": threshold,
                "model": config.name,
            },
        )
        if not isinstance(response, list):
            raise ValueError("NER endpoint returned non-list payload")
        return response

    async def check_health(self, model_type: str) -> bool:
        config = getattr(self, model_type, None)
        if not config or not config.endpoint:
            return False
        try:
            await self._get(f"{config.endpoint}/health", timeout=2.0)
            return True
        except Exception:
            return False

    async def _post(self, url: str, payload: dict) -> Any:
        response = await self._client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def _get(self, url: str, timeout: float | None = None) -> dict:
        response = await self._client.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        if not self.llm:
            raise RuntimeError("No LLM model configured")

        config = self.llm
        response = await self._post(
            f"{config.endpoint}/v1/chat/completions",
            {
                "model": config.name,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens if max_tokens is not None else settings.llm_max_tokens,
                "temperature": (
                    temperature if temperature is not None else settings.llm_temperature
                ),
            },
        )
        return str(response["choices"][0]["message"]["content"])


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
    ner = None
    if settings.ner_endpoint:
        ner = ModelConfig(
            name=settings.ner_model,
            endpoint=settings.ner_endpoint,
            protocol=settings.ner_protocol,
        )
    llm = None
    if settings.llm_endpoint:
        llm = ModelConfig(
            name=settings.llm_model,
            endpoint=settings.llm_endpoint,
            protocol="openai",
            timeout=60.0,
        )

    return ModelGateway(embedding=embedding, reranker=reranker, ner=ner, llm=llm)
