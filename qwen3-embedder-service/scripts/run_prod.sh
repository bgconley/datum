#!/bin/bash
# Production server with auto-detection

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Production settings
export QWEN_EMBED_BACKEND="${QWEN_EMBED_BACKEND:-auto}"
export QWEN_EMBED_LOG_FORMAT="${QWEN_EMBED_LOG_FORMAT:-json}"
export QWEN_EMBED_LOG_LEVEL="${QWEN_EMBED_LOG_LEVEL:-INFO}"
export QWEN_EMBED_HOST="${QWEN_EMBED_HOST:-0.0.0.0}"
export QWEN_EMBED_PORT="${QWEN_EMBED_PORT:-8010}"

# CUDA optimization
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Starting qwen3-embedder in production mode..."
echo "Backend: $QWEN_EMBED_BACKEND"
echo "Host: $QWEN_EMBED_HOST:$QWEN_EMBED_PORT"

python -m qwen3_embedder.main
