"""Dependency management and venv bootstrapping for vision-tools MCP server."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger("vision-tools")

VENV_DIR = Path.home() / ".vision-tools-env"
VENV_PYTHON = VENV_DIR / "bin" / "python3"
SETUP_SCRIPT = Path(__file__).parent / "setup.sh"


def _check_dependencies() -> str | None:
    """Check if all required packages are importable. Returns error message or None."""
    missing = []
    try:
        import mcp  # noqa: F401
    except ImportError:
        missing.append("mcp")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")

    if missing:
        return (
            f"Missing packages: {', '.join(missing)}\n"
            f"\n"
            f"Run the setup script to install everything:\n"
            f"  bash {SETUP_SCRIPT}\n"
            f"\n"
            f"Or install manually into the venv:\n"
            f"  {VENV_DIR}/bin/pip3 install {' '.join(missing)}\n"
        )
    return None


def _auto_setup() -> bool:
    """Attempt automatic setup if the venv doesn't exist. Returns True if setup ran."""
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        return False  # Venv exists, deps might just be missing

    if not SETUP_SCRIPT.exists():
        return False

    _log.info("First run — setting up virtualenv...")
    try:
        result = subprocess.run(
            ["bash", str(SETUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            _log.info("Setup complete!")
            return True
        _log.error("Setup failed:\n%s", result.stderr)
        return False
    except (OSError, subprocess.SubprocessError) as e:
        _log.error("Setup error: %s", e)
        return False


def _relaunch_in_venv() -> None:
    """Re-launch this script using the venv Python if we're not already in it."""
    # Already in venv?
    if sys.prefix != sys.base_prefix:
        return
    if not VENV_PYTHON.exists():
        return

    # Re-exec with venv python
    try:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])
    except OSError as e:
        _log.error("Failed to relaunch in venv (%s): %s", VENV_PYTHON, e)
        sys.exit(1)


def ensure_dependencies() -> None:
    """Ensure venv exists and dependencies are installed. Exits on failure."""
    _relaunch_in_venv()

    if _check_dependencies():
        if _auto_setup():
            _relaunch_in_venv()

        err = _check_dependencies()
        if err:
            _log.error("%s", err)
            sys.exit(1)
