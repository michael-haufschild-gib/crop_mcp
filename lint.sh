#!/usr/bin/env bash
# Run the same local gates as CI, sequentially, and report every failed gate.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

venv_dir="${VENV:-.vision-tools-env}"
if [[ ! -x "$venv_dir/bin/ruff" || ! -x "$venv_dir/bin/mypy" || ! -x "$venv_dir/bin/pytest" ]]; then
    echo "Development tools are missing. Run make setup first." >&2
    exit 1
fi

failed=0
for target in lint format-check typecheck test; do
    make VENV="$venv_dir" "$target" || failed=1
done

while IFS= read -r -d '' file; do
    lines=$(wc -l < "$file")
    if (( lines > 750 )); then
        echo "$file has $lines lines (maximum 750)" >&2
        failed=1
    fi
done < <(find . \( -name .git -o -name .venv -o -name .vision-tools-env -o -name __pycache__ \) \
    -prune -o -name '*.py' -type f -print0)

exit "$failed"
