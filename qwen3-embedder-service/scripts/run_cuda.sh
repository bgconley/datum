#!/bin/bash
# Run with PyTorch CUDA backend

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# CUDA-specific settings
export QWEN_EMBED_BACKEND=pytorch
export QWEN_EMBED_PROFILE="${QWEN_EMBED_PROFILE:-qwen3_4b_cuda}"
export QWEN_EMBED_LOG_FORMAT="${QWEN_EMBED_LOG_FORMAT:-json}"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

echo "Starting qwen3-embedder with PyTorch CUDA backend..."
echo "Profile: $QWEN_EMBED_PROFILE"

python -m qwen3_embedder.main
