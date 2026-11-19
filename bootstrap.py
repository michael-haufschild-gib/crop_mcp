"""Use the host's Python environment, with a portable fallback for source checkouts."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from importlib.util import find_spec
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
VENV_DIR = Path.home() / ".vision-tools-env"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python3")


def setup_environment(*, dev: bool = False) -> None:
    """Install the checkout into the environment used by existing host registrations."""
    if not VENV_PYTHON.is_file():
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    project = f"{PROJECT}[dev]" if dev else str(PROJECT)
    subprocess.run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--upgrade-strategy",
            "eager",
            "-c",
            str(PROJECT / "requirements.lock"),
            "-e",
            project,
        ],
        stdout=sys.stderr,
        check=True,
    )


def ensure_dependencies() -> None:
    if all(find_spec(name) is not None for name in ("pymcp", "PIL", "numpy")):
        return
    in_project_env = Path(sys.prefix).resolve() == VENV_DIR.resolve()
    if in_project_env or not VENV_PYTHON.is_file():
        setup_environment()
    if not in_project_env:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])
