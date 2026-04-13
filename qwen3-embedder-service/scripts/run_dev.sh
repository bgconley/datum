#!/bin/bash
# Development server with auto-reload

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set development defaults
export QWEN_EMBED_LOG_FORMAT="${QWEN_EMBED_LOG_FORMAT:-console}"
export QWEN_EMBED_LOG_LEVEL="${QWEN_EMBED_LOG_LEVEL:-DEBUG}"
export QWEN_EMBED_BACKEND="${QWEN_EMBED_BACKEND:-auto}"

echo "Starting qwen3-embedder in development mode..."
echo "Backend: $QWEN_EMBED_BACKEND"
echo "Log format: $QWEN_EMBED_LOG_FORMAT"

# Run with uvicorn reload
python -m uvicorn qwen3_embedder.main:create_app \
    --factory \
    --host "${QWEN_EMBED_HOST:-127.0.0.1}" \
    --port "${QWEN_EMBED_PORT:-8010}" \
    --reload \
    --reload-dir src
