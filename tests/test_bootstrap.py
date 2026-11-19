"""The host chooses the interpreter. Checkout installation reserves stdout for MCP."""

import sys
from pathlib import Path
from unittest.mock import patch

from bootstrap import ensure_dependencies, setup_environment
from server import main


def test_host_with_dependencies_starts_without_install_or_reexec() -> None:
    with (
        patch("bootstrap.setup_environment") as install,
        patch("os.execv") as reexec,
        patch("server._start_server") as start,
        patch("sys.argv", ["server.py"]),
    ):
        main()
    install.assert_not_called()
    reexec.assert_not_called()
    start.assert_called_once()


def test_checkout_with_existing_environment_reuses_its_interpreter(tmp_path: Path) -> None:
    python = tmp_path / "python"
    python.touch()
    with (
        patch("bootstrap.find_spec", return_value=None),
        patch("bootstrap.VENV_PYTHON", python),
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("bootstrap.setup_environment") as install,
        patch("os.execv") as reexec,
        patch("sys.argv", ["server.py"]),
    ):
        ensure_dependencies()
    reexec.assert_called_once_with(str(python), [str(python), "server.py"])
    install.assert_not_called()


def test_first_checkout_install_uses_lock_and_keeps_stdout_clean(tmp_path: Path) -> None:
    with (
        patch("bootstrap.VENV_PYTHON", tmp_path / "absent"),
        patch("bootstrap.VENV_DIR", tmp_path),
        patch("venv.EnvBuilder.create") as create,
        patch("subprocess.run") as install,
    ):
        setup_environment()
    create.assert_called_once_with(tmp_path)
    command = install.call_args.args[0]
    assert Path(command[command.index("-c") + 1]).name == "requirements.lock"
    assert install.call_args.kwargs["stdout"] is sys.stderr


def test_explicit_dev_setup_exits_before_serving() -> None:
    with (
        patch("sys.argv", ["server.py", "--setup", "--dev"]),
        patch("server.setup_environment") as install,
        patch("server._start_server") as start,
    ):
        main()
    install.assert_called_once_with(dev=True)
    start.assert_not_called()
