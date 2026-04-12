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
BACKEND_DIR="$(cd "$SCRIPT_DIR/../backend" && pwd)"

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

echo ""
echo "=== Bootstrap Complete ==="
echo "Venv: $VENV_PATH"
echo "Python: $(python --version)"
echo "Pip packages:"
pip list --format=columns | grep -E "^(datum|fastapi|sqlalchemy|alembic|pytest|asyncpg|pydantic|watchdog|pyyaml)" || true
echo ""
echo "To activate manually: source $VENV_PATH/bin/activate"
echo "To run tests: source $VENV_PATH/bin/activate && cd $BACKEND_DIR && pytest tests/ -v"
