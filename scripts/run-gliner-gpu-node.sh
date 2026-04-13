#!/usr/bin/env bash
# datum/scripts/run-gliner-gpu-node.sh
#
# Runs the Datum GLiNER service from its dedicated GPU-node venv.
#
# Usage:
#   CUDA_VISIBLE_DEVICES=1 DATUM_GLINER_DEVICE=cuda:0 DATUM_GLINER_HOST=0.0.0.0 \
#     bash scripts/run-gliner-gpu-node.sh

set -euo pipefail

VENV_PATH="${DATUM_GLINER_VENV:-/tank/venvs/datum-gliner}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_DIR="$REPO_DIR/gliner-ner-service"

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "FATAL: GLiNER venv not found at $VENV_PATH"
    echo "Run: bash scripts/bootstrap-gliner-gpu-node.sh"
    exit 1
fi

if [ ! -d "$SERVICE_DIR" ]; then
    echo "FATAL: GLiNER service directory not found at $SERVICE_DIR"
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

cd "$SERVICE_DIR"

export DATUM_GLINER_HOST="${DATUM_GLINER_HOST:-0.0.0.0}"
export DATUM_GLINER_PORT="${DATUM_GLINER_PORT:-8012}"
export DATUM_GLINER_MODEL_ID="${DATUM_GLINER_MODEL_ID:-knowledgator/gliner-bi-large-v2.0}"
export DATUM_GLINER_LOG_LEVEL="${DATUM_GLINER_LOG_LEVEL:-info}"

exec ./scripts/run_prod.sh
