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
