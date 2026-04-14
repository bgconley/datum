from unittest.mock import AsyncMock, patch

import pytest

from datum.services.model_gateway import ModelConfig, ModelGateway


class TestModelGateway:
    @pytest.fixture
    def gateway(self):
        return ModelGateway(
            embedding=ModelConfig(
                name="test-embed",
                endpoint="http://localhost:8010",
                protocol="openai",
                dimensions=1024,
                batch_size=32,
            )
        )

    @pytest.mark.asyncio
    async def test_embed_single(self, gateway: ModelGateway):
        mock_response = {
            "data": [{"embedding": [0.1] * 1024, "index": 0}],
            "usage": {"total_tokens": 10},
        }
        with patch.object(
            ModelGateway,
            "_post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await gateway.embed(["hello world"])
            assert len(result) == 1
            assert len(result[0]) == 1024
        await gateway.close()

    @pytest.mark.asyncio
    async def test_embed_batch(self, gateway: ModelGateway):
        mock_response = {
            "data": [
                {"embedding": [0.1] * 1024, "index": 0},
                {"embedding": [0.2] * 1024, "index": 1},
            ],
            "usage": {"total_tokens": 20},
        }
        with patch.object(
            ModelGateway,
            "_post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await gateway.embed(["text one", "text two"])
            assert len(result) == 2
        await gateway.close()

    @pytest.mark.asyncio
    async def test_health_check(self, gateway: ModelGateway):
        with patch.object(
            ModelGateway,
            "_get",
            new_callable=AsyncMock,
            return_value={"status": "ok"},
        ):
            healthy = await gateway.check_health("embedding")
            assert healthy is True
        await gateway.close()

    @pytest.mark.asyncio
    async def test_embed_query_with_custom_service_protocol(self):
        gateway = ModelGateway(
            embedding=ModelConfig(
                name="Qwen3-Embedding-4B",
                endpoint="http://localhost:8010",
                protocol="qwen3_embedder",
                dimensions=1024,
                batch_size=32,
            )
        )
        with patch.object(
            ModelGateway,
            "_post",
            new_callable=AsyncMock,
            return_value={"data": [{"embedding": [0.1] * 1024, "index": 0}]},
        ) as mocked_post:
            result = await gateway.embed(
                ["where is the migration?"], input_type="query", instruction="find docs"
            )
            assert len(result) == 1
            payload = mocked_post.await_args.args[1]
            assert payload["input_type"] == "query"
            assert payload["instruction"] == "find docs"
            assert payload["dimensions"] == 1024
        await gateway.close()

    @pytest.mark.asyncio
    async def test_rerank_custom_service_protocol(self):
        gateway = ModelGateway(
            reranker=ModelConfig(
                name="Qwen3-Reranker-0.6B",
                endpoint="http://localhost:8011",
                protocol="qwen3_reranker",
            )
        )
        with patch.object(
            ModelGateway,
            "_post",
            new_callable=AsyncMock,
            return_value={
                "results": [
                    {"index": 2, "relevance_score": 0.95},
                    {"index": 0, "relevance_score": 0.75},
                ]
            },
        ):
            result = await gateway.rerank("query", ["a", "b", "c"], top_n=2)
            assert result == [(2, 0.95), (0, 0.75)]
        await gateway.close()

    @pytest.mark.asyncio
    async def test_generate_uses_openai_chat_completions(self):
        gateway = ModelGateway(
            llm=ModelConfig(
                name="gpt-oss-20b",
                endpoint="http://localhost:8000",
                protocol="openai",
            )
        )
        with patch.object(
            ModelGateway,
            "_post",
            new_callable=AsyncMock,
            return_value={"choices": [{"message": {"content": "Hello world"}}]},
        ) as mocked_post:
            result = await gateway.generate("Say hello", max_tokens=32, temperature=0.2)
            assert result == "Hello world"
            payload = mocked_post.await_args.args[1]
            assert payload["messages"][0]["content"] == "Say hello"
            assert payload["max_tokens"] == 32
            assert payload["temperature"] == 0.2
        await gateway.close()
