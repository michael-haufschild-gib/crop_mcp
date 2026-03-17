"""Tests for bootstrap.py — dependency checking, auto-setup, and venv relaunching."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bootstrap import _auto_setup, _check_dependencies, _relaunch_in_venv, ensure_dependencies


class TestCheckDependencies:
    """Tests for _check_dependencies."""

    def test_returns_none_when_all_present(self) -> None:
        # All three packages are installed in the test venv
        assert _check_dependencies() is None

    def test_returns_message_when_mcp_missing(self) -> None:
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "mcp":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _check_dependencies()
            assert result is not None
            assert "mcp" in result
            assert "Missing packages" in result


class TestAutoSetup:
    """Tests for _auto_setup."""

    def test_returns_false_when_venv_exists(self, tmp_path: Path) -> None:
        venv = tmp_path / "venv"
        venv.mkdir()
        python = venv / "bin" / "python3"
        python.parent.mkdir(parents=True)
        python.touch()

        with patch("bootstrap.VENV_DIR", venv), patch("bootstrap.VENV_PYTHON", python):
            assert _auto_setup() is False

    def test_returns_false_when_setup_script_missing(self, tmp_path: Path) -> None:
        venv = tmp_path / "nonexistent-venv"
        python = venv / "bin" / "python3"
        script = tmp_path / "nonexistent-setup.sh"

        with (
            patch("bootstrap.VENV_DIR", venv),
            patch("bootstrap.VENV_PYTHON", python),
            patch("bootstrap.SETUP_SCRIPT", script),
        ):
            assert _auto_setup() is False

    def test_returns_true_on_successful_setup(self, tmp_path: Path) -> None:
        venv = tmp_path / "nonexistent-venv"
        python = venv / "bin" / "python3"
        script = tmp_path / "setup.sh"
        script.write_text("#!/bin/bash\nexit 0\n")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("bootstrap.VENV_DIR", venv),
            patch("bootstrap.VENV_PYTHON", python),
            patch("bootstrap.SETUP_SCRIPT", script),
            patch("subprocess.run", return_value=mock_result) as mock_run,
        ):
            assert _auto_setup() is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0] == ["bash", str(script)]
            assert call_args[1]["timeout"] == 120

    def test_returns_false_on_failed_setup(self, tmp_path: Path) -> None:
        venv = tmp_path / "nonexistent-venv"
        python = venv / "bin" / "python3"
        script = tmp_path / "setup.sh"
        script.write_text("#!/bin/bash\nexit 1\n")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "setup failed"

        with (
            patch("bootstrap.VENV_DIR", venv),
            patch("bootstrap.VENV_PYTHON", python),
            patch("bootstrap.SETUP_SCRIPT", script),
            patch("subprocess.run", return_value=mock_result),
        ):
            assert _auto_setup() is False

    def test_returns_false_on_subprocess_exception(self, tmp_path: Path) -> None:
        venv = tmp_path / "nonexistent-venv"
        python = venv / "bin" / "python3"
        script = tmp_path / "setup.sh"
        script.write_text("#!/bin/bash\nexit 0\n")

        with (
            patch("bootstrap.VENV_DIR", venv),
            patch("bootstrap.VENV_PYTHON", python),
            patch("bootstrap.SETUP_SCRIPT", script),
            patch("subprocess.run", side_effect=OSError("exec failed")),
        ):
            assert _auto_setup() is False


class TestRelaunchInVenv:
    """Tests for _relaunch_in_venv guard conditions."""

    def test_noop_when_already_in_venv(self) -> None:
        # sys.prefix != sys.base_prefix means we're already in a venv
        # In the test environment, we ARE in a venv, so execv should not be called
        with patch("os.execv") as mock_execv:
            _relaunch_in_venv()
            mock_execv.assert_not_called()

    def test_noop_when_venv_python_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent" / "bin" / "python3"
        with (
            patch("sys.prefix", "/usr"),
            patch("sys.base_prefix", "/usr"),
            patch("bootstrap.VENV_PYTHON", missing),
            patch("os.execv") as mock_execv,
        ):
            _relaunch_in_venv()
            mock_execv.assert_not_called()

    def test_calls_execv_when_outside_venv_and_python_exists(self, tmp_path: Path) -> None:
        fake_python = tmp_path / "bin" / "python3"
        fake_python.parent.mkdir(parents=True)
        fake_python.touch()

        with (
            patch("sys.prefix", "/usr"),
            patch("sys.base_prefix", "/usr"),
            patch("bootstrap.VENV_PYTHON", fake_python),
            patch("os.execv") as mock_execv,
        ):
            _relaunch_in_venv()
            mock_execv.assert_called_once()
            args = mock_execv.call_args[0]
            assert args[0] == str(fake_python)


class TestEnsureDependencies:
    """Tests for ensure_dependencies orchestration."""

    def test_exits_when_deps_missing_and_no_auto_setup(self) -> None:
        with (
            patch("bootstrap._relaunch_in_venv"),
            patch("bootstrap._check_dependencies", return_value="Missing: mcp"),
            patch("bootstrap._auto_setup", return_value=False),
            pytest.raises(SystemExit, match="1"),
        ):
            ensure_dependencies()

    def test_succeeds_when_deps_present(self) -> None:
        with (
            patch("bootstrap._relaunch_in_venv"),
            patch("bootstrap._check_dependencies", return_value=None),
        ):
            # Should not raise or exit
            ensure_dependencies()

    def test_retries_after_auto_setup(self) -> None:
        # First call: deps missing. After auto_setup: deps present.
        check_results = iter(["Missing: mcp", None])

        with (
            patch("bootstrap._relaunch_in_venv"),
            patch("bootstrap._check_dependencies", side_effect=lambda: next(check_results)),
            patch("bootstrap._auto_setup", return_value=True),
        ):
            ensure_dependencies()
