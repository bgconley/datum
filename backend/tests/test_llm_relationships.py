"""Tests for LLM relationship extraction helpers."""

import json

from datum.services.llm_relationships import build_relationship_prompt, parse_relationship_response


def test_build_relationship_prompt_includes_text_and_entities():
    prompt = build_relationship_prompt(
        "FastAPI uses PostgreSQL for persistence.",
        ["FastAPI", "PostgreSQL"],
    )
    assert "FastAPI uses PostgreSQL" in prompt
    assert "FastAPI, PostgreSQL" in prompt


def test_parse_relationship_response_filters_invalid_items():
    response = json.dumps(
        {
            "relationships": [
                {
                    "source_entity": "FastAPI",
                    "target_entity": "PostgreSQL",
                    "relationship_type": "uses",
                    "evidence_text": "FastAPI uses PostgreSQL",
                    "confidence": 0.9,
                },
                {
                    "source_entity": "A",
                    "target_entity": "B",
                    "relationship_type": "invalid",
                    "evidence_text": "bad",
                    "confidence": 1.0,
                },
            ]
        }
    )
    result = parse_relationship_response(response)
    assert len(result) == 1
    assert result[0].relationship_type == "uses"


def test_parse_relationship_response_handles_markdown_fences():
    response = """```json
    {
      "relationships": [
        {
          "source_entity": "A",
          "target_entity": "B",
          "relationship_type": "depends_on",
          "evidence_text": "A depends on B",
          "confidence": 0.8
        }
      ]
    }
    ```"""
    result = parse_relationship_response(response)
    assert len(result) == 1
    assert result[0].source_entity == "A"
