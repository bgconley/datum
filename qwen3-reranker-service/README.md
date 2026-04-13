# Qwen3 Reranker Service (Datum)

Standalone reranker service for Datum with an OpenAI-style `/v1/rerank` endpoint.

## Datum contract

- Default port: `8011`
- Default profile: `qwen3_06b_cuda`
- Datum protocol value: `qwen3_reranker`
- Response score field: `relevance_score`
- Supports optional `instruction` for task-specific reranking behavior.

## Quick start

```bash
cd qwen3-reranker-service
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[cuda]"
./scripts/run_prod.sh
```

Smoke check:

```bash
curl http://127.0.0.1:8011/health
curl -X POST http://127.0.0.1:8011/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "capital of france",
    "documents": [
      "Paris is the capital of France.",
      "Berlin is the capital of Germany."
    ]
  }'
```

## Configuration

Environment variables:

- `QWEN_RERANK_BACKEND` (`auto|pytorch|vllm|mlx`, default `auto`)
- `QWEN_RERANK_PROFILE` (default `qwen3_06b_cuda`)
- `QWEN_RERANK_HOST` (default `0.0.0.0`)
- `QWEN_RERANK_PORT` (default `8011`)
- `QWEN_RERANK_LOG_LEVEL` (default `INFO`)
- `QWEN_RERANK_LOG_FORMAT` (`json|console`, default `json`)

Profiles are defined in [config/reranker_profiles.yaml](config/reranker_profiles.yaml).

## Running modes

```bash
# Auto-detect backend
./scripts/run_dev.sh

# CUDA/PyTorch
./scripts/run_cuda.sh

# vLLM
./scripts/run_vllm.sh

# Production (no reload)
./scripts/run_prod.sh
```

Docker:

```bash
docker build -t qwen3-reranker:cuda .
docker run --gpus all -p 8011:8011 qwen3-reranker:cuda
```

## Datum backend integration

Set Datum backend env values:

```bash
DATUM_RERANKER_PROVIDER=external
DATUM_RERANKER_PROTOCOL=qwen3_reranker
DATUM_RERANKER_API_URL=http://127.0.0.1:8011/v1/rerank
DATUM_RERANKER_MODEL=Qwen/Qwen3-Reranker-0.6B
```

## API summary

- `POST /v1/rerank`
- `GET /health`
- `GET /healthz`
- `GET /ready`
- `GET /v1/config`

Response payload:

```json
{
  "results": [
    {"index": 0, "relevance_score": 0.98}
  ],
  "model": "Qwen/Qwen3-Reranker-0.6B",
  "meta": {
    "max_length": 8192,
    "batch_size": 8,
    "scoring": "p_yes_softmax(no,yes)",
    "truncated_docs": 0,
    "elapsed_ms": 35.2
  }
}
```

## Validation

```bash
python3 -m pytest -q
python3 -m ruff check src tests
```
