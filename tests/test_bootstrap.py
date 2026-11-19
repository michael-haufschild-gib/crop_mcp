"""The host chooses the interpreter. Checkout installation reserves stdout for MCP."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import pytest

from bootstrap import (
    MIN_PYTHON,
    PROJECT,
    _dependencies_ready,
    _install_in_checkout,
    _python_candidates,
    ensure_dependencies,
    ensure_python,
    setup_environment,
)
from server import main


def test_host_with_dependencies_starts_without_install_or_reexec() -> None:
    with (
        patch("bootstrap.setup_environment") as install,
        patch("bootstrap._launch") as reexec,
        patch("server._start_server") as start,
        patch("sys.argv", ["server.py"]),
    ):
        main()
    install.assert_not_called()
    reexec.assert_not_called()
    start.assert_called_once()


def test_checkout_with_existing_environment_reuses_its_interpreter(tmp_path: Path) -> None:
    with (
        patch("bootstrap._dependencies_ready", return_value=False),
        patch("bootstrap.VENV_PYTHON", Path(sys.executable)),
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("bootstrap._launch") as reexec,
        patch("bootstrap._env_accepts", return_value=True),
        patch("subprocess.run") as run,
    ):
        ensure_dependencies()
    reexec.assert_called_once_with(sys.executable)
    run.assert_not_called()


def test_incompatible_installed_package_does_not_count_as_ready() -> None:
    def stale(name: str) -> str:
        return "1.0" if name == "numpy" else version(name)

    with patch("importlib.metadata.version", side_effect=stale):
        assert not _dependencies_ready()


def test_existing_registration_can_use_its_previous_environment_offline(tmp_path: Path) -> None:
    with (
        patch("bootstrap._dependencies_ready", return_value=False),
        patch("bootstrap.VENV_PYTHON", tmp_path / "absent"),
        patch("bootstrap._LEGACY_PYTHON", Path(sys.executable)),
        patch("bootstrap._env_accepts", return_value=True),
        patch("bootstrap.setup_environment") as install,
        patch("bootstrap._launch") as launch,
    ):
        ensure_dependencies()
    launch.assert_called_once_with(sys.executable)
    install.assert_not_called()


def test_setup_reports_launchable_paths_and_keeps_stdout_clean(tmp_path: Path) -> None:
    script = str(PROJECT / "server.py")
    result = subprocess.run(
        [sys.executable, script, "--setup"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
    config = json.loads(result.stderr[result.stderr.index("{") :])
    entry = config["mcpServers"]["vision-tools"]
    assert [entry["command"], *entry["args"]] == [sys.executable, script]
    if os.name != "nt":
        for client in ("claude", "codex"):
            command = next(line for line in result.stderr.splitlines() if line.startswith(client))
            assert shlex.split(command.split(" -- ", 1)[1]) == [sys.executable, script]


def test_old_python_finds_versioned_command_on_path(tmp_path: Path) -> None:
    versioned = tmp_path / ("python3.12.exe" if os.name == "nt" else "python3.12")
    versioned.touch()
    with patch.dict(os.environ, PATH=str(tmp_path)):
        assert [str(versioned)] in list(_python_candidates())
    with (
        patch("sys.version_info", (3, 11)),
        patch("bootstrap._python_candidates", return_value=iter([[sys.executable]])),
        patch("bootstrap._launch") as launch,
    ):
        ensure_python()
    launch.assert_called_once_with(sys.executable)


def test_old_python_without_candidate_explains_required_version() -> None:
    spec = tomllib.loads((PROJECT / "pyproject.toml").read_text())["project"]["requires-python"]
    assert spec == ">=" + ".".join(map(str, MIN_PYTHON))
    with (
        patch("sys.version_info", (3, 11)),
        patch("bootstrap._python_candidates", return_value=iter([])),
        pytest.raises(SystemExit, match=r"Python 3\.12 or newer.*server\.py --setup"),
    ):
        ensure_python()


def test_first_checkout_install_uses_lock_and_keeps_stdout_clean(tmp_path: Path) -> None:
    with (
        patch("bootstrap.VENV_PYTHON", tmp_path / "absent"),
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("subprocess.run") as install,
    ):
        _install_in_checkout(dev=False)
    create = install.call_args_list[0]
    assert create.args[0] == [sys.executable, "-m", "venv", str(tmp_path)]
    assert create.kwargs["stdout"] is sys.stderr
    command = install.call_args.args[0]
    assert Path(command[command.index("-c") + 1]).name == "requirements.lock"
    assert install.call_args.kwargs["stdout"] is sys.stderr


def test_explicit_dev_setup_exits_before_serving() -> None:
    with (
        patch("sys.argv", ["server.py", "--setup", "--dev"]),
        patch("bootstrap.setup_environment") as install,
        patch("server._start_server") as start,
    ):
        main()
    install.assert_called_once_with(dev=True)
    start.assert_not_called()


def test_installer_owns_setup_independently_of_the_host_pipe() -> None:
    with patch("subprocess.run") as run:
        setup_environment(dev=True)
    assert run.call_args.args[0] == [
        sys.executable,
        str(PROJECT / "bootstrap.py"),
        "--install",
        "--dev",
    ]
    assert run.call_args.kwargs["stdin"] == subprocess.DEVNULL


def test_interrupted_install_forces_repair_before_reuse(tmp_path: Path) -> None:
    marker = tmp_path / ".installing"
    marker.touch()
    with (
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("bootstrap._env_accepts", return_value=True),
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "pip")),
        pytest.raises(subprocess.CalledProcessError),
    ):
        _install_in_checkout(dev=False)
    assert marker.exists()
    with (
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("bootstrap._env_accepts", return_value=True),
        patch("subprocess.run") as pip,
    ):
        _install_in_checkout(dev=False)
    assert "--force-reinstall" in pip.call_args.args[0]
    assert not marker.exists()


def test_another_process_cannot_enter_a_live_setup_lock(tmp_path: Path) -> None:
    from bootstrap import _setup_lock

    probe = """
from pathlib import Path
import sys
from file_lock import exclusive
try:
    with exclusive(Path(sys.argv[1]), 0):
        pass
except TimeoutError:
    sys.exit(23)
"""
    command = [sys.executable, "-c", probe, str(tmp_path / ".setup.lock")]
    with patch("bootstrap.VENV_DIR", tmp_path), _setup_lock():
        assert subprocess.run(command, cwd=PROJECT, check=False).returncode == 23
    assert subprocess.run(command, cwd=PROJECT, check=False).returncode == 0
