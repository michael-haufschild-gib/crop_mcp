#!/usr/bin/env bash
# Lint all Python files: ruff check + format check + max file length.
set -euo pipefail

VENV_DIR="$HOME/.vision-tools-env"
RUFF="$VENV_DIR/bin/ruff"
MYPY="$VENV_DIR/bin/mypy"
PYTEST="$VENV_DIR/bin/pytest"
MAX_LINES=750
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

fail=0

# --- Verify tools are installed ---
if [ ! -f "$RUFF" ] || [ ! -f "$MYPY" ] || [ ! -f "$PYTEST" ]; then
    echo -e "${RED}Dev tools missing. Run: bash setup.sh${NC}"
    exit 1
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

# --- Mypy ---
echo "=== mypy ==="
if [ -f "$MYPY" ]; then
    if "$MYPY" .; then
        echo -e "${GREEN}mypy: passed${NC}"
    else
        fail=1
    fi
else
    echo -e "${RED}mypy not installed. Run: bash setup.sh${NC}"
    fail=1
fi

echo ""

# --- Pytest ---
echo "=== pytest ==="
if [ -f "$PYTEST" ]; then
    if "$PYTEST" --tb=short -q --cov; then
        echo -e "${GREEN}pytest: passed${NC}"
    else
        fail=1
    fi
else
    echo -e "${RED}pytest not installed. Run: bash setup.sh${NC}"
    fail=1
fi

echo ""
if [ "$fail" -eq 0 ]; then
    echo -e "${GREEN}All checks passed.${NC}"
else
    echo -e "${RED}Some checks failed.${NC}"
    exit 1
fi
