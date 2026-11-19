#!/usr/bin/env bash
# Install development dependencies using the same Python setup as the MCP host.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for python_cmd in python3.14 python3 python; do
    if command -v "$python_cmd" >/dev/null && "$python_cmd" -c 'import sys; sys.exit(sys.version_info < (3, 14))'; then
        exec "$python_cmd" "$project_dir/server.py" --setup --dev
    fi
done
echo "Python 3.14 or newer is required. See https://www.python.org/downloads/" >&2
exit 1
