from unittest.mock import AsyncMock, Mock

import pytest

from datum.services.entity_extraction import (
    ENTITY_LABELS,
    EntityCandidate,
    _parse_entities,
    extract_entities_gliner,
    normalize_entity_name,
)


class TestNormalizeEntityName:
    def test_strips_whitespace_and_punctuation(self):
        assert normalize_entity_name("  PostgreSQL.  ") == "postgresql"
        assert normalize_entity_name(" Redis,") == "redis"

    def test_collapses_known_variants(self):
        assert normalize_entity_name("Postgres") == "postgresql"
        assert normalize_entity_name("k8s") == "kubernetes"


class TestParseEntities:
    def test_deduplicates_and_orders_entities(self):
        entities = _parse_entities(
            [
                {"text": "Redis", "label": "technology", "start": 41, "end": 46, "score": 0.92},
                {
                    "text": "PostgreSQL",
                    "label": "technology",
                    "start": 7,
                    "end": 17,
                    "score": 0.95,
                },
                {
                    "text": "PostgreSQL",
                    "label": "technology",
                    "start": 7,
                    "end": 17,
                    "score": 0.91,
                },
            ]
        )

        assert entities == [
            EntityCandidate(
                canonical_name="postgresql",
                raw_text="PostgreSQL",
                entity_type="technology",
                start_char=7,
                end_char=17,
                confidence=0.95,
            ),
            EntityCandidate(
                canonical_name="redis",
                raw_text="Redis",
                entity_type="technology",
                start_char=41,
                end_char=46,
                confidence=0.92,
            ),
        ]


class TestExtractEntitiesGliner:
    @pytest.mark.asyncio
    async def test_extracts_entities_from_http_payload(self):
        response = Mock()
        response.json.return_value = [
            {"text": "PostgreSQL", "label": "technology", "start": 7, "end": 17, "score": 0.95},
            {"text": "Redis", "label": "technology", "start": 22, "end": 27, "score": 0.92},
        ]
        response.raise_for_status = Mock()

        client = AsyncMock()
        client.post.return_value = response

        entities = await extract_entities_gliner(
            "We use PostgreSQL and Redis.",
            client=client,
            endpoint="http://test:8012",
        )

        assert [entity.canonical_name for entity in entities] == ["postgresql", "redis"]
        assert entities[0].entity_type == "technology"
        assert entities[0].start_char == 7

    @pytest.mark.asyncio
    async def test_handles_empty_or_failed_responses(self):
        empty_response = Mock()
        empty_response.json.return_value = []
        empty_response.raise_for_status = Mock()

        empty_client = AsyncMock()
        empty_client.post.return_value = empty_response

        heuristic_entities = await extract_entities_gliner(
            "Redis warms PostgreSQL query results.",
            client=empty_client,
            endpoint="http://test:8012",
        )
        assert [entity.canonical_name for entity in heuristic_entities] == ["redis", "postgresql"]

        failing_client = AsyncMock()
        failing_client.post.side_effect = RuntimeError("connection refused")

        fallback_entities = await extract_entities_gliner(
            "ParadeDB depends on PostgreSQL.",
            client=failing_client,
            endpoint="http://test:8012",
        )
        assert [entity.canonical_name for entity in fallback_entities] == [
            "paradedb",
            "postgresql",
        ]

    @pytest.mark.asyncio
    async def test_merges_heuristic_software_entities_with_gliner_output(self):
        response = Mock()
        response.json.return_value = [
            {"text": "April 13, 2026", "label": "date", "start": 32, "end": 46, "score": 0.91},
        ]
        response.raise_for_status = Mock()

        client = AsyncMock()
        client.post.return_value = response

        entities = await extract_entities_gliner(
            "Redis shipped a cache update on April 13, 2026.",
            client=client,
            endpoint="http://test:8012",
        )

        assert [entity.canonical_name for entity in entities] == ["redis", "april 13, 2026"]
        assert entities[0].extraction_method == "heuristic_technical"
        assert entities[1].entity_type == "date"

    def test_entity_labels_cover_design_types(self):
        assert "technology" in ENTITY_LABELS
        assert "service" in ENTITY_LABELS
        assert "person" in ENTITY_LABELS
        assert "architecture component" in ENTITY_LABELS
