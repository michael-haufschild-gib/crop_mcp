"""Use the host's Python environment, with a portable fallback for source checkouts."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from file_lock import exclusive

if TYPE_CHECKING:
    from collections.abc import Iterator

PROJECT = Path(__file__).resolve().parent
VENV_DIR = PROJECT / ".vision-tools-env"
_PYTHON_PATH = Path("Scripts/python.exe" if os.name == "nt" else "bin/python3")
VENV_PYTHON = VENV_DIR / _PYTHON_PATH
_LEGACY_PYTHON = Path.home() / ".vision-tools-env" / _PYTHON_PATH
_CHECK_DEPENDENCIES = (
    "from bootstrap import _dependencies_ready; sys.exit(not _dependencies_ready())"
)
MIN_PYTHON = (3, 12)


def _launch(python: str) -> None:
    args = [python, str(PROJECT / "server.py"), *sys.argv[1:]]
    if os.name == "nt":
        raise SystemExit(subprocess.call(args))
    os.execv(python, args)


def _python_candidates() -> Iterator[list[str]]:
    yield [str(VENV_PYTHON)]
    if os.name == "nt":
        yield ["py", "-3"]
    yield ["python3"]
    yield ["python"]
    for directory in os.get_exec_path():
        for path in Path(directory).glob("python3.*"):
            if re.fullmatch(r"python3\.\d+(?:\.exe)?", path.name, re.IGNORECASE):
                yield [str(path.absolute())]
    if shutil.which("uv"):
        found = subprocess.run(
            ["uv", "python", "find", "--no-project", "--no-python-downloads", ">=3.12"],
            capture_output=True,
            text=True,
            check=False,
        )
        if found.returncode == 0:
            yield [found.stdout.strip()]
    yield [str(_LEGACY_PYTHON)]


def ensure_python() -> None:
    """Keep the invoking Python when supported, otherwise locate an installed one."""
    if sys.version_info[:2] >= MIN_PYTHON:
        return
    probe = (
        f"import sys\nif sys.version_info[:2] < {MIN_PYTHON}: sys.exit(1)\nprint(sys.executable)"
    )
    for command in _python_candidates():
        if shutil.which(command[0]):
            try:
                result = subprocess.run(
                    [*command, "-c", probe], capture_output=True, text=True, check=False
                )
            except OSError:
                continue
            if result.returncode == 0 and result.stdout.strip():
                _launch(result.stdout.strip())
                return
    raise SystemExit(
        f"Vision Tools needs Python 3.12 or newer. This is Python {sys.version.split()[0]}. "
        "Run server.py --setup with the full path to a compatible Python, "
        "or install one from https://www.python.org/downloads/."
    )


def _dependencies_ready() -> bool:
    import tomllib
    from importlib.metadata import requires, version

    try:
        from packaging.requirements import Requirement

        metadata = PROJECT / "pyproject.toml"
        if metadata.is_file():
            specs = tomllib.loads(metadata.read_text(encoding="utf-8"))["project"]["dependencies"]
        else:
            specs = requires("vision-tools-mcp") or []
        for spec in specs:
            req = Requirement(spec)
            if (req.marker is None or req.marker.evaluate()) and version(
                req.name
            ) not in req.specifier:
                return False
    except ImportError:
        return False
    return True


@contextmanager
def _setup_lock() -> Iterator[None]:
    """Serialize installations from clients starting the same checkout together."""
    VENV_DIR.mkdir(exist_ok=True)
    with exclusive(VENV_DIR / ".setup.lock", timeout=300):
        yield


def _env_accepts(python: Path, check: str) -> bool:
    """Probe a virtual environment before using it for this checkout."""
    if not python.is_file():
        return False
    probe = (
        "import sys\n"
        f"if sys.prefix == sys.base_prefix or sys.version_info[:2] < {MIN_PYTHON}: sys.exit(1)\n"
        + check
    )
    try:
        result = subprocess.run(
            [str(python), "-c", probe],
            cwd=PROJECT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return result.returncode == 0


def _host_ready() -> bool:
    if Path(sys.prefix).resolve() != VENV_DIR:
        return _dependencies_ready()
    with _setup_lock():
        return not (VENV_DIR / ".installing").exists() and _dependencies_ready()


def _install_in_checkout(*, dev: bool) -> None:
    project = f"{PROJECT}[dev]" if dev else str(PROJECT)
    marker = VENV_DIR / ".installing"
    with _setup_lock():
        repair = marker.exists()
        if not repair and not dev and _env_accepts(VENV_PYTHON, _CHECK_DEPENDENCIES):
            return
        marker.touch()
        if not _env_accepts(VENV_PYTHON, "import pip"):
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                stdin=subprocess.DEVNULL,
                stdout=sys.stderr,
                check=True,
            )
        subprocess.run(
            [
                str(VENV_PYTHON),
                "-m",
                "pip",
                "--require-virtualenv",
                "--no-input",
                "install",
                *(["--force-reinstall"] if repair else []),
                "-c",
                str(PROJECT / "requirements.lock"),
                "-e",
                project,
            ],
            stdin=subprocess.DEVNULL,
            stdout=sys.stderr,
            check=True,
        )
        marker.unlink()


def setup_environment(*, dev: bool = False) -> None:
    """Let one installer own the checkout lock even if its launching client exits."""
    if not dev and VENV_PYTHON.is_file():
        with _setup_lock():
            if not (VENV_DIR / ".installing").exists() and _env_accepts(
                VENV_PYTHON, _CHECK_DEPENDENCIES
            ):
                return
    if not (PROJECT / "requirements.lock").is_file():
        raise SystemExit("Reinstall vision-tools-mcp with the package manager that installed it.")
    try:
        subprocess.run(
            [
                sys.executable,
                str(PROJECT / "bootstrap.py"),
                "--install",
                *(["--dev"] if dev else []),
            ],
            stdin=subprocess.DEVNULL,
            stdout=sys.stderr,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"Could not prepare {VENV_DIR}. Fix the error and rerun server.py --setup.\n{exc}"
        ) from exc


def configure_host(*, dev: bool) -> None:
    """Report the actual paths the client should launch after successful setup."""
    if dev or not _host_ready():
        setup_environment(dev=dev)
        python = str(VENV_PYTHON)
    else:
        python = sys.executable
    script = str(PROJECT / "server.py")
    args = [python, script]
    quoted = (
        " ".join("'" + arg.replace("'", "''") + "'" for arg in args)
        if os.name == "nt"
        else shlex.join(args)
    )
    config = {"mcpServers": {"vision-tools": {"command": python, "args": [script]}}}
    sys.stderr.write(
        f"\nClaude Code:\nclaude mcp add --transport stdio --scope user vision-tools -- {quoted}\n"
        f"\nCodex:\ncodex mcp add vision-tools -- {quoted}\n"
        f"\nClaude Desktop / Antigravity:\n{json.dumps(config, indent=2)}\n"
    )


def ensure_dependencies() -> None:
    """Serve directly in a compatible host or switch to the checkout environment."""
    if _host_ready():
        return
    if not VENV_PYTHON.is_file() and _env_accepts(_LEGACY_PYTHON, _CHECK_DEPENDENCIES):
        _launch(str(_LEGACY_PYTHON))
        return
    setup_environment()
    _launch(str(VENV_PYTHON))


if __name__ == "__main__" and "--install" in sys.argv:
    _install_in_checkout(dev="--dev" in sys.argv)
