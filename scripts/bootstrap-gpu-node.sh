#!/usr/bin/env bash
# datum/scripts/bootstrap-gpu-node.sh
#
# Creates or updates the dedicated datum venv on the GPU node.
# Run this once after cloning, and again after changing backend dependencies.
#
# Usage: bash scripts/bootstrap-gpu-node.sh
#
# Venv path: /tank/venvs/datum (persistent ZFS, outside repo)
# Installs: backend/.[dev] (datum package + test dependencies)

set -euo pipefail

VENV_PATH="/tank/venvs/datum"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"
ENV_FILE="$REPO_DIR/.env"

echo "=== Datum GPU Node Bootstrap ==="
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "Venv: $VENV_PATH"
echo "Backend: $BACKEND_DIR"
echo ""

# Verify Python 3.11+ is available
PYTHON=""
for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
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

# Create venv parent directory if needed (may require sudo the first time)
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

# Create or update venv
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo "Creating venv at $VENV_PATH..."
    "$PYTHON" -m venv "$VENV_PATH"
else
    echo "Venv exists at $VENV_PATH, updating..."
fi

# Activate and install
source "$VENV_PATH/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip --quiet

echo "Installing datum backend[dev]..."
pip install -e "$BACKEND_DIR[dev]" --quiet

detect_host_ip() {
    local detected
    detected="${DATUM_HOST_IP:-}"
    if [ -n "$detected" ]; then
        printf "%s\n" "$detected"
        return
    fi

    detected="$("$PYTHON" - <<'PY' 2>/dev/null || true
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
finally:
    s.close()
PY
)"

    if [ -z "$detected" ]; then
        detected="host.docker.internal"
    fi
    printf "%s\n" "$detected"
}

write_env_var() {
    local key="$1"
    local value="$2"
    local tmp
    tmp="$(mktemp)"

    if [ -f "$ENV_FILE" ]; then
        grep -v "^${key}=" "$ENV_FILE" > "$tmp" || true
    fi

    printf "%s=%s\n" "$key" "$value" >> "$tmp"
    mv "$tmp" "$ENV_FILE"
}

echo "Writing GPU node compose env to $ENV_FILE..."
HOST_IP="$(detect_host_ip)"
write_env_var "DATUM_UID" "$(id -u)"
write_env_var "DATUM_GID" "$(id -g)"
write_env_var "DATUM_PROJECTS_ROOT" "/tank/datum/projects"
write_env_var "DATUM_BLOBS_ROOT" "/tank/datum/blobs"
write_env_var "DATUM_CACHE_ROOT" "/tank/datum/cache"
write_env_var "DATUM_PGDATA" "/tank/datum/pgdata"
write_env_var "DATUM_EMBEDDING_ENDPOINT" "http://${HOST_IP}:8010"
write_env_var "DATUM_EMBEDDING_MODEL" "Qwen3-Embedding-4B"
write_env_var "DATUM_EMBEDDING_DIMENSIONS" "1024"
write_env_var "DATUM_EMBEDDING_PROTOCOL" "openai"
write_env_var "DATUM_EMBEDDING_BATCH_SIZE" "64"
write_env_var "DATUM_RERANKER_ENDPOINT" "http://${HOST_IP}:8011"
write_env_var "DATUM_RERANKER_MODEL" "Qwen3-Reranker-0.6B"
write_env_var "DATUM_RERANKER_PROTOCOL" "openai"

echo ""
echo "=== Bootstrap Complete ==="
echo "Venv: $VENV_PATH"
echo "Compose env: $ENV_FILE"
echo "Python: $(python --version)"
echo "Model endpoints: embed=http://${HOST_IP}:8010 rerank=http://${HOST_IP}:8011"
echo "Pip packages:"
pip list --format=columns | grep -E "^(datum|fastapi|sqlalchemy|alembic|pytest|asyncpg|pydantic|watchdog|pyyaml)" || true
echo ""
echo "To activate manually: source $VENV_PATH/bin/activate"
echo "To run tests: source $VENV_PATH/bin/activate && cd $BACKEND_DIR && pytest tests/ -v"
echo "Compose will use: DATUM_UID=$(id -u) DATUM_GID=$(id -g)"
