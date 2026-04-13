#!/bin/bash
# Run with MLX backend (Apple Silicon)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# MLX-specific settings
export QWEN_EMBED_BACKEND=mlx
export QWEN_EMBED_PROFILE="${QWEN_EMBED_PROFILE:-qwen3_4b_mlx}"
export QWEN_EMBED_LOG_FORMAT="${QWEN_EMBED_LOG_FORMAT:-console}"

echo "Starting qwen3-embedder with MLX backend..."
echo "Profile: $QWEN_EMBED_PROFILE"

python -m qwen3_embedder.main
