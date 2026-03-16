#!/usr/bin/env bash
# Lint all Python files: ruff check + format check + max file length.
set -euo pipefail

VENV_DIR="$HOME/.vision-tools-env"
RUFF="$VENV_DIR/bin/ruff"
MAX_LINES=750
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

fail=0

# --- Ensure ruff is installed ---
if [ ! -f "$RUFF" ]; then
    echo "Installing ruff..."
    "$VENV_DIR/bin/pip3" install ruff --quiet
fi

cd "$SCRIPT_DIR"

# --- Ruff lint ---
echo "=== ruff check ==="
if "$RUFF" check .; then
    echo -e "${GREEN}ruff check: passed${NC}"
else
    fail=1
fi

echo ""

# --- Ruff format check ---
echo "=== ruff format --check ==="
if "$RUFF" format --check .; then
    echo -e "${GREEN}ruff format: passed${NC}"
else
    echo -e "${RED}Run: $RUFF format . to fix${NC}"
    fail=1
fi

echo ""

# --- Max file length ---
echo "=== file length (max $MAX_LINES lines) ==="
over_limit=0
for f in $(find . -name '*.py' -not -path './.git/*' -not -path '*__pycache__*'); do
    lines=$(wc -l < "$f")
    if [ "$lines" -gt "$MAX_LINES" ]; then
        echo -e "${RED}OVER LIMIT: $f ($lines lines, max $MAX_LINES)${NC}"
        over_limit=1
    fi
done

if [ "$over_limit" -eq 0 ]; then
    echo -e "${GREEN}file length: all files under $MAX_LINES lines${NC}"
else
    fail=1
fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo -e "${GREEN}All checks passed.${NC}"
else
    echo -e "${RED}Some checks failed.${NC}"
    exit 1
fi
