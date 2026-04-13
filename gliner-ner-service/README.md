# Datum GLiNER NER Service

Native FastAPI service for Phase 5 entity extraction.

## Contract

- `GET /health`
- `POST /extract`

Request:

```json
{
  "text": "Use PostgreSQL and Redis.",
  "labels": ["technology", "service"],
  "threshold": 0.5
}
```

Response:

```json
[
  {
    "text": "PostgreSQL",
    "label": "technology",
    "start": 4,
    "end": 14,
    "score": 0.95
  }
]
```

## Local development

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check src tests
uv run mypy src
```

## GPU-node runtime

Install with PyTorch runtime extras:

```bash
uv sync --extra pytorch --extra dev
```

Run:

```bash
./scripts/run_prod.sh
```
