#!/usr/bin/env bash
# datum/scripts/bootstrap-gliner-gpu-node.sh
#
# Creates or updates a dedicated GPU-node venv for the Datum GLiNER service.
#
# Usage: bash scripts/bootstrap-gliner-gpu-node.sh

set -euo pipefail

VENV_PATH="${DATUM_GLINER_VENV:-/tank/venvs/datum-gliner}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_DIR="$REPO_DIR/gliner-ner-service"

echo "=== Datum GLiNER GPU Node Bootstrap ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Venv: $VENV_PATH"
echo "Service: $SERVICE_DIR"
echo ""

PYTHON=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "FATAL: Python >= 3.11 not found on this system."
    echo "Install with: sudo apt install python3.12 python3.12-venv python3.12-dev"
    exit 1
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"

VENV_PARENT="$(dirname "$VENV_PATH")"
if [ ! -d "$VENV_PARENT" ]; then
    echo "Venv parent directory $VENV_PARENT does not exist."
    echo "Create it with: sudo mkdir -p $VENV_PARENT && sudo chown \$(whoami) $VENV_PARENT"
    exit 1
fi
if [ ! -w "$VENV_PARENT" ]; then
    echo "Venv parent directory $VENV_PARENT is not writable by $(whoami)."
    echo "Fix with: sudo chown $(whoami) $VENV_PARENT"
    exit 1
fi

if [ ! -d "$SERVICE_DIR" ]; then
    echo "FATAL: GLiNER service directory not found at $SERVICE_DIR"
    exit 1
fi

if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating venv at $VENV_PATH..."
    "$PYTHON" -m venv "$VENV_PATH"
else
    echo "Venv exists at $VENV_PATH, updating..."
fi

# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install uv into the dedicated venv if it is unavailable so we can honor uv.lock.
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv into GLiNER venv..."
    pip install "uv>=0.5,<1.0" --quiet
fi

echo "Installing gliner-ner-service from uv.lock (frozen)..."
(
    cd "$SERVICE_DIR"
    uv sync --frozen --active --extra pytorch --extra dev
)

echo ""
echo "=== Bootstrap Complete ==="
echo "Venv: $VENV_PATH"
echo "Python: $(python --version)"
echo "Installed packages:"
pip list --format=columns | grep -E "^(gliner|gliner-ner-service|torch|transformers|fastapi|uvicorn)" || true
echo ""
echo "Recommended GPU-node launch:"
echo "  CUDA_VISIBLE_DEVICES=1 DATUM_GLINER_DEVICE=cuda:0 DATUM_GLINER_HOST=0.0.0.0 bash scripts/run-gliner-gpu-node.sh"
