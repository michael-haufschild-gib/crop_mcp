#!/usr/bin/env bash
# Install development dependencies using the same Python setup as the MCP host.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for python_cmd in python3 python $(compgen -c | grep -E '^python3\.[0-9]+$' | sort -u); do
    if command -v "$python_cmd" >/dev/null && "$python_cmd" -c 'import sys; sys.exit(sys.version_info < (3, 8))'; then
        exec "$python_cmd" "$project_dir/server.py" --setup --dev
    fi
done
if command -v uv >/dev/null && python_cmd="$(uv python find --no-project --no-python-downloads '>=3.12')"; then
    exec "$python_cmd" "$project_dir/server.py" --setup --dev
fi
echo "Run server.py --setup --dev with an installed Python 3.12 or newer. See https://www.python.org/downloads/" >&2
exit 1
