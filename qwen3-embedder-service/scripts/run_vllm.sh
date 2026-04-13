#!/bin/bash
# Run with vLLM backend (high-throughput CUDA)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# vLLM-specific settings
export QWEN_EMBED_BACKEND=vllm
export QWEN_EMBED_PROFILE="${QWEN_EMBED_PROFILE:-qwen3_4b_vllm}"
export QWEN_EMBED_LOG_FORMAT="${QWEN_EMBED_LOG_FORMAT:-json}"
export VLLM_WORKER_MULTIPROC_METHOD=spawn

echo "Starting qwen3-embedder with vLLM backend..."
echo "Profile: $QWEN_EMBED_PROFILE"

python -m qwen3_embedder.main
