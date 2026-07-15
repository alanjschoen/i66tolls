from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from i66tolls.api import Interchange
from i66tolls.wizard import (
    Step,
    WizardState,
    build_initial_state,
    compute_steps,
    is_complete,
    show_chart_result,
    show_result,
)

EASTERN = ZoneInfo("US/Eastern")


def test_compute_steps_for_historic_includes_datetime() -> None:
    state = WizardState(
        mode="historic",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=16,
        exit_name="Washington",
    )
    steps = compute_steps(state)
    assert Step.MODE in steps
    assert Step.DIRECTION in steps
    assert Step.WEEKDAY not in steps
    assert Step.DATETIME in steps


def test_compute_steps_for_chart_includes_weekday() -> None:
    state = WizardState(mode="chart")
    steps = compute_steps(state)
    assert steps == [
        Step.MODE,
        Step.DIRECTION,
        Step.WEEKDAY,
        Step.ENTRY,
        Step.EXIT,
    ]


def test_compute_steps_for_current_skips_direction_and_datetime() -> None:
    state = WizardState(
        mode="current",
        direction="eastbound",
        at=datetime.now(EASTERN),
    )
    steps = compute_steps(state)
    assert Step.DIRECTION not in steps
    assert Step.DATETIME not in steps
    assert Step.ENTRY in steps


def test_is_complete_historic_requires_datetime() -> None:
    state = WizardState(
        mode="historic",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
    )
    assert not is_complete(state)


def test_is_complete_historic_with_datetime() -> None:
    state = WizardState(
        mode="historic",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
        at=datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN),
    )
    assert is_complete(state)


def test_is_complete_chart_requires_weekday() -> None:
    state = WizardState(
        mode="chart",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
        exit_name="Westmoreland St",
    )
    assert not is_complete(state)


@patch("i66tolls.wizard.list_exits", return_value=[(10, "Westmoreland St")])
@patch("i66tolls.wizard.lookup_entry", return_value=Interchange(1, "I-66 West", "eastbound"))
@patch("i66tolls.wizard.infer_direction", return_value="eastbound")
def test_build_initial_state_from_cli_args(
    _infer: object,
    _lookup: object,
    _exits: object,
) -> None:
    state = build_initial_state(
        entry_id=1,
        exit_id=10,
        at=None,
        direction=None,
        mode="current",
    )
    assert state.entry is not None
    assert state.exit_id == 10
    assert state.mode == "current"
    assert Step.ENTRY in state.skip_prompt
    assert Step.EXIT in state.skip_prompt


def test_build_initial_state_entry_requires_direction() -> None:
    with pytest.raises(ValueError, match="entry requires"):
        build_initial_state(
            entry_id=1,
            exit_id=None,
            at=None,
            direction=None,
            mode=None,
        )


@patch("i66tolls.wizard.get_toll", return_value=4.5)
def test_show_result_formats_toll(_get_toll: object) -> None:
    state = WizardState(
        mode="historic",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
        exit_name="Westmoreland St",
        at=datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN),
    )
    with patch("typer.echo") as echo:
        show_result(state)
    echo.assert_called_once()
    assert "$4.50" in echo.call_args.args[0]
    assert "06/10/2026 08:00 AM" in echo.call_args.args[0]


@patch("i66tolls.wizard.get_toll", return_value=None)
def test_show_result_data_not_available(_get_toll: object) -> None:
    state = WizardState(
        mode="historic",
        direction="eastbound",
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
        exit_name="Westmoreland St",
        at=datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN),
    )
    with patch("typer.echo") as echo:
        show_result(state)
    assert "Data Not Available" in echo.call_args.args[0]


@patch("i66tolls.wizard.show_price_chart")
@patch("i66tolls.wizard.get_route_zones", return_value=(0, 1))
@patch("i66tolls.wizard.fetch_price_trends")
def test_show_chart_result(
    fetch_trends: object,
    _zones: object,
    show_chart: object,
) -> None:
    trends = fetch_trends.return_value
    trends.week_count = 4
    trends.series.return_value = (("08:00 AM",), (2.5,))

    state = WizardState(
        mode="chart",
        direction="eastbound",
        weekday=0,
        entry=Interchange(1, "I-66 West", "eastbound"),
        exit_id=10,
        exit_name="Westmoreland St",
    )
    show_chart_result(state)
    show_chart.assert_called_once()
