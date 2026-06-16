from unittest.mock import patch

from typer.testing import CliRunner

from i66tolls.cli import app

runner = CliRunner()


def test_help_short_and_long() -> None:
    assert runner.invoke(app, ["-h"]).exit_code == 0
    assert runner.invoke(app, ["--help"]).exit_code == 0


def test_conflicting_direction_flags() -> None:
    result = runner.invoke(app, ["-e", "-w"])
    assert result.exit_code == 1
    assert "cannot be used together" in result.output


def test_conflicting_time_flags() -> None:
    result = runner.invoke(app, ["-c", "-t", "06/10/2026 08:00 AM"])
    assert result.exit_code == 1
    assert "cannot be used together" in result.output


def test_partial_entry_exit_arguments() -> None:
    result = runner.invoke(app, ["1"])
    assert result.exit_code == 1
    assert "both entry and exit" in result.output


@patch("i66tolls.cli.run")
def test_non_interactive_invocation_calls_run(run: object) -> None:
    result = runner.invoke(app, ["1", "10", "-c"])
    assert result.exit_code == 0
    run.assert_called_once()
