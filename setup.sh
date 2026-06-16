#!/usr/bin/env bash
# Vision Tools MCP — Setup Script
# Creates a virtualenv and installs dependencies.
# Safe to re-run: reuses the venv and upgrades dependencies.

set -euo pipefail

VENV_DIR="$HOME/.vision-tools-env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_PYTHON_VERSION="3.14"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }

# --- Find Python ---
find_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" -c "import sys; raise SystemExit(sys.version_info < (3, 14))" 2>/dev/null; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD=$(find_python) || {
    error "Python $REQUIRED_PYTHON_VERSION+ is required but not found."
    echo ""
    echo "  Install Python:"
    echo "    macOS:   brew install python3"
    echo "    Ubuntu:  sudo apt install python3"
    echo "    Windows: https://www.python.org/downloads/"
    echo ""
    exit 1
}

PYTHON_VERSION=$("$PYTHON_CMD" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
info "Found Python $PYTHON_VERSION at $(which "$PYTHON_CMD")"

# --- Create virtualenv ---
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python3" ]; then
    info "Virtualenv already exists at $VENV_DIR"
else
    warn "Creating virtualenv at $VENV_DIR ..."
    "$PYTHON_CMD" -m venv "$VENV_DIR" || {
        error "Failed to create virtualenv."
        echo ""
        echo "  Try installing the venv module:"
        echo "    macOS:   (included with Homebrew Python)"
        echo "    Ubuntu:  sudo apt install python3-venv"
        echo ""
        exit 1
    }
    info "Virtualenv created at $VENV_DIR"
fi

# --- Install dependencies ---
PIP="$VENV_DIR/bin/pip3"
PYTHON="$VENV_DIR/bin/python3"

# Upgrade pip first (silently)
"$PIP" install --upgrade pip --quiet 2>/dev/null || true

# Install all deps from pyproject.toml. Eager upgrades are intentional: rerunning
# setup should refresh old transitive dependencies, not only install missing ones.
warn "Installing dependencies from pyproject.toml ..."
"$PIP" install --upgrade --upgrade-strategy eager -e "$SCRIPT_DIR[dev]" --quiet || {
    error "Failed to install dependencies."
    echo ""
    echo "  Try running manually:"
    echo "    $PIP install --upgrade --upgrade-strategy eager -e \"$SCRIPT_DIR[dev]\""
    echo ""
    exit 1
}
info "Dependencies installed"

# --- Verify installation ---
"$PYTHON" -c "
import mcp
from PIL import Image
import numpy
print('All imports OK')
" || {
    error "Import verification failed. Try removing $VENV_DIR and re-running this script."
    exit 1
}

info "Setup complete!"
echo ""
echo "  Server:  $PYTHON $SCRIPT_DIR/server.py"
echo "  Venv:    $VENV_DIR"
echo ""
echo "  Add to ~/.claude/settings.json:"
echo '  {'
echo '    "mcpServers": {'
echo '      "vision-tools": {'
echo "        \"command\": \"$VENV_DIR/bin/python3\","
echo "        \"args\": [\"$SCRIPT_DIR/server.py\"]"
echo '      }'
echo '    }'
echo '  }'
