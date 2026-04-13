#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"

if [ -d ".venv" ]; then
    # Local development convenience; GPU-node wrappers may activate a separate venv first.
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
fi

export DATUM_GLINER_HOST="${DATUM_GLINER_HOST:-127.0.0.1}"
export DATUM_GLINER_PORT="${DATUM_GLINER_PORT:-8012}"
export DATUM_GLINER_MODEL_ID="${DATUM_GLINER_MODEL_ID:-knowledgator/gliner-bi-large-v2.0}"
export DATUM_GLINER_LOG_LEVEL="${DATUM_GLINER_LOG_LEVEL:-info}"

echo "Starting Datum GLiNER NER service"
echo "  Host: ${DATUM_GLINER_HOST}:${DATUM_GLINER_PORT}"
echo "  Model: ${DATUM_GLINER_MODEL_ID}"
echo "  Device: ${DATUM_GLINER_DEVICE:-auto}"
echo ""

exec python -m gliner_ner_service.app
