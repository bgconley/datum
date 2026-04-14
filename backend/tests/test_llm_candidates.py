"""Tests for LLM candidate extraction helpers."""

import json

from datum.services.llm_candidates import build_candidate_prompt, parse_candidate_response


def test_build_candidate_prompt_includes_doc_type():
    prompt = build_candidate_prompt("We decided to use PostgreSQL.", "decision")
    assert "decision" in prompt
    assert "We decided to use PostgreSQL." in prompt


def test_parse_candidate_response_filters_low_confidence_and_invalid_types():
    response = json.dumps(
        {
            "candidates": [
                {
                    "type": "decision",
                    "title": "Use PostgreSQL",
                    "description": "Use PostgreSQL for durability.",
                    "evidence_text": "We decided to use PostgreSQL.",
                    "confidence": 0.9,
                },
                {
                    "type": "invalid",
                    "title": "Bad",
                    "description": "",
                    "evidence_text": "",
                    "confidence": 0.9,
                },
                {
                    "type": "requirement",
                    "title": "Weak",
                    "description": "Maybe this matters.",
                    "evidence_text": "Maybe",
                    "confidence": 0.2,
                },
            ]
        }
    )
    result = parse_candidate_response(response)
    assert len(result) == 1
    assert result[0].candidate_type == "decision"


def test_parse_candidate_response_handles_markdown_fences():
    response = """```json
    {
      "candidates": [
        {
          "type": "open_question",
          "title": "Caching strategy",
          "description": "Should we use Redis?",
          "evidence_text": "Should we use Redis?",
          "confidence": 0.8
        }
      ]
    }
    ```"""
    result = parse_candidate_response(response)
    assert len(result) == 1
    assert result[0].candidate_type == "open_question"
