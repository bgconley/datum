# Qwen3 Embedder Service (Datum)

Standalone embedding service for Datum with an OpenAI-compatible `/v1/embeddings` endpoint.

## Datum contract

- Default port: `8010`
- Default profile: `qwen3_4b_cuda`
- Datum protocol value: `qwen3_embedder`
- Query/document behavior:
  - `input_type=document` keeps text unchanged
  - `input_type=query` applies query instruction formatting
  - Explicit `instruction` overrides default query instruction
- Matryoshka support: Datum can request `dimensions=1024`.

## Quick start

```bash
cd qwen3-embedder-service
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[cuda]"
./scripts/run_prod.sh
```

Smoke check:

```bash
curl http://127.0.0.1:8010/health
curl -X POST http://127.0.0.1:8010/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": ["test query"],
    "input_type": "query",
    "dimensions": 1024
  }'
```

## Configuration

Environment variables:

- `QWEN_EMBED_BACKEND` (`auto|pytorch|vllm|mlx`, default `auto`)
- `QWEN_EMBED_PROFILE` (default `qwen3_4b_cuda`)
- `QWEN_EMBED_HOST` (default `0.0.0.0`)
- `QWEN_EMBED_PORT` (default `8010`)
- `QWEN_EMBED_LOG_LEVEL` (default `INFO`)
- `QWEN_EMBED_LOG_FORMAT` (`json|console`, default `json`)

Profiles are defined in [config/embedder_profiles.yaml](config/embedder_profiles.yaml).

## Running modes

```bash
# Auto-detect backend
./scripts/run_dev.sh

# CUDA/PyTorch
./scripts/run_cuda.sh

# Production (no reload)
./scripts/run_prod.sh
```

Docker:

```bash
docker build -t qwen3-embedder:cuda .
docker run --gpus all -p 8010:8010 qwen3-embedder:cuda
```

## Datum backend integration

Set Datum backend env values:

```bash
DATUM_EMBEDDING_PROVIDER=external
DATUM_EMBEDDING_PROTOCOL=qwen3_embedder
DATUM_EMBEDDING_API_URL=http://127.0.0.1:8010/v1/embeddings
DATUM_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B
DATUM_EMBEDDING_DIMENSIONS=1024
```

## API summary

- `POST /v1/embeddings`
- `GET /health`
- `GET /healthz`
- `GET /ready`
- `GET /v1/models`

Response payload follows OpenAI-style embeddings schema (`data[].embedding`, `usage`, `model`).

## Validation

```bash
python3 -m pytest -q
python3 -m ruff check src tests
```
