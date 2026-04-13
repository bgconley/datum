#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$ROOT_DIR"
uv run --extra dev uvicorn gliner_ner_service.app:create_app --factory --reload --host 127.0.0.1 --port 8012
