#!/usr/bin/env bash
# Vision Tools MCP — Setup Script
# Creates a virtualenv and installs dependencies.
# Safe to re-run: skips steps that are already done.

set -euo pipefail

VENV_DIR="$HOME/.vision-tools-env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_PYTHON_VERSION="3.9"

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
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            if [ -n "$ver" ]; then
                local major minor
                major=$(echo "$ver" | cut -d. -f1)
                minor=$(echo "$ver" | cut -d. -f2)
                if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
                    echo "$cmd"
                    return 0
                fi
            fi
        fi
    done
    return 1
}

PYTHON_CMD=$(find_python) || {
    error "Python 3.9+ is required but not found."
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

# Check installed version against a minimum. Returns 0 if satisfied, 1 otherwise.
# Usage: check_pkg_version <pip_name> <min_major> <min_minor>
check_pkg_version() {
    local pkg="$1" min_major="$2" min_minor="$3"
    local ver
    ver=$("$PIP" show "$pkg" 2>/dev/null | grep '^Version:' | awk '{print $2}')
    if [ -z "$ver" ]; then
        return 1  # not installed
    fi
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -gt "$min_major" ] 2>/dev/null; then
        return 0
    elif [ "$major" -eq "$min_major" ] && [ "$minor" -ge "$min_minor" ] 2>/dev/null; then
        return 0
    fi
    return 1  # version too old
}

# (pip_name, install_spec, min_major, min_minor)
DEPS_SPEC=(
    "mcp:mcp[cli]:1:0"
    "Pillow:Pillow:10:0"
    "numpy:numpy:1:24"
)
DEV_DEPS=("pytest" "pytest-cov" "mypy" "ruff" "types-Pillow")
MISSING=()

for spec in "${DEPS_SPEC[@]}"; do
    IFS=':' read -r pkg_name install_name min_major min_minor <<< "$spec"
    if ! check_pkg_version "$pkg_name" "$min_major" "$min_minor"; then
        MISSING+=("$install_name")
    fi
done

if [ ${#MISSING[@]} -eq 0 ]; then
    info "All dependencies already installed"
else
    warn "Installing: ${MISSING[*]} ..."
    "$PIP" install "${MISSING[@]}" --quiet || {
        error "Failed to install dependencies."
        echo ""
        echo "  Try running manually:"
        echo "    $PIP install ${MISSING[*]}"
        echo ""
        exit 1
    }
    info "Dependencies installed"
fi

# --- Install dev dependencies ---
DEV_MISSING=()

for dep in "${DEV_DEPS[@]}"; do
    if ! "$PIP" show "$dep" &>/dev/null; then
        DEV_MISSING+=("$dep")
    fi
done

if [ ${#DEV_MISSING[@]} -eq 0 ]; then
    info "All dev dependencies already installed"
else
    warn "Installing dev deps: ${DEV_MISSING[*]} ..."
    "$PIP" install "${DEV_MISSING[@]}" --quiet || {
        error "Failed to install dev dependencies."
        echo ""
        echo "  Try running manually:"
        echo "    $PIP install ${DEV_MISSING[*]}"
        echo ""
        exit 1
    }
    info "Dev dependencies installed"
fi

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
