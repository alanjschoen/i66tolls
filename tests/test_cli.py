from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from typer.testing import CliRunner

from i66tolls.cli import app, scrape_app, show_state

runner = CliRunner()
EASTERN = ZoneInfo("US/Eastern")


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
@patch(
    "i66tolls.cli.build_initial_state",
    side_effect=lambda **kwargs: kwargs,
)
def test_non_interactive_invocation_calls_run(
    build_state: object, run: object
) -> None:
    result = runner.invoke(app, ["1", "10", "-c"])
    assert result.exit_code == 0
    build_state.assert_called_once()
    run.assert_called_once()


def test_state_conflicts_with_other_options() -> None:
    result = runner.invoke(app, ["--state", "-c"])
    assert result.exit_code == 1
    assert "--state cannot be combined" in result.output


@patch("i66tolls.cli.show_state")
def test_state_flag_calls_show_state(show: object) -> None:
    result = runner.invoke(app, ["--state"])
    assert result.exit_code == 0
    show.assert_called_once_with()


@patch("i66tolls.cli.get_zone_prices", return_value=(1.05, 2.0, 2.75, 10.0))
@patch("i66tolls.cli.active_direction", return_value="eastbound")
def test_show_state_prints_time_and_prices(
    _direction: object, _prices: object, capsys: object
) -> None:
    at = datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN)
    show_state(at=at)
    output = capsys.readouterr().out
    assert output == "06/10/2026 08:00 AM\n[1.05, 2.00, 2.75, 10.00]\n"


@patch("i66tolls.cli.get_zone_prices")
@patch("i66tolls.cli.active_direction", return_value=None)
def test_show_state_outside_hours_prints_time_only(
    _direction: object, prices: object, capsys: object
) -> None:
    at = datetime(2026, 6, 10, 12, 0, tzinfo=EASTERN)
    show_state(at=at)
    output = capsys.readouterr().out
    assert output == "06/10/2026 12:00 PM\n"
    prices.assert_not_called()


def test_scrape_dry_run(tmp_path) -> None:
    result = runner.invoke(
        scrape_app,
        ["1 week", "--dry-run", "--data-dir", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "planned:" in result.output

