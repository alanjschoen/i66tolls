"""Interactive toll lookup wizard."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Literal, Optional
from zoneinfo import ZoneInfo

import typer

from i66tolls import prompts
from i66tolls.api import (
    Interchange,
    _entries_for_direction,
    get_route_zones,
    get_toll,
    infer_direction,
    list_exits,
    lookup_entry,
)
from i66tolls.chart import show_price_chart
from i66tolls.hours import (
    EASTBOUND_LABEL,
    WESTBOUND_LABEL,
    active_direction,
    toll_window_active,
)
from i66tolls.prompts import GoBack, Quit
from i66tolls.trends import fetch_price_trends

EASTERN = ZoneInfo("US/Eastern")
Direction = Literal["eastbound", "westbound"]
Mode = Literal["current", "historic", "chart"]


class Step(Enum):
    MODE = auto()
    DIRECTION = auto()
    WEEKDAY = auto()
    ENTRY = auto()
    EXIT = auto()
    DATETIME = auto()


@dataclass
class WizardState:
    mode: Optional[Mode] = None
    direction: Optional[Direction] = None
    weekday: Optional[int] = None
    entry: Optional[Interchange] = None
    exit_id: Optional[int] = None
    exit_name: Optional[str] = None
    at: Optional[datetime] = None
    skip_prompt: set[Step] = field(default_factory=set)


def build_initial_state(
    *,
    entry_id: Optional[int],
    exit_id: Optional[int],
    at: Optional[datetime],
    direction: Optional[Direction],
    mode: Optional[Mode],
) -> WizardState:
    state = WizardState()
    now = datetime.now(EASTERN)

    if mode is not None:
        state.mode = mode
        state.skip_prompt.add(Step.MODE)

    if mode == "current":
        state.at = now
        state.skip_prompt.add(Step.DIRECTION)
        state.skip_prompt.add(Step.DATETIME)

    if at is not None:
        state.mode = "historic"
        state.at = at.astimezone(EASTERN) if at.tzinfo else at.replace(tzinfo=EASTERN)
        state.skip_prompt.add(Step.MODE)
        state.skip_prompt.add(Step.DATETIME)

    if direction is not None:
        state.direction = direction
        state.skip_prompt.add(Step.DIRECTION)

    if entry_id is not None and exit_id is not None:
        inferred = infer_direction(entry_id, exit_id)
        state.direction = inferred
        state.entry = lookup_entry(entry_id, inferred)
        state.exit_id = exit_id
        for exit_option_id, exit_option_name in list_exits(state.entry):
            if exit_option_id == exit_id:
                state.exit_name = exit_option_name
                break
        state.skip_prompt.add(Step.ENTRY)
        state.skip_prompt.add(Step.EXIT)
    elif entry_id is not None:
        if state.direction is None:
            raise ValueError(
                "entry requires --eastbound/--westbound or an exit to infer direction"
            )
        state.entry = lookup_entry(entry_id, state.direction)
        state.skip_prompt.add(Step.ENTRY)

    return state


def compute_steps(state: WizardState) -> list[Step]:
    steps: list[Step] = [Step.MODE]
    if state.mode == "current":
        steps.extend([Step.ENTRY, Step.EXIT])
        return steps
    if state.mode in ("historic", "chart"):
        steps.append(Step.DIRECTION)
    if state.mode == "chart":
        steps.append(Step.WEEKDAY)
    steps.extend([Step.ENTRY, Step.EXIT])
    if state.mode == "historic" and state.at is None:
        steps.append(Step.DATETIME)
    return steps


def _clear_from(state: WizardState, step: Step) -> None:
    if step == Step.MODE:
        state.mode = None
        state.direction = None
        state.weekday = None
        state.at = None
        state.entry = None
        state.exit_id = None
        state.exit_name = None
    elif step == Step.DIRECTION:
        state.direction = None
        state.weekday = None
        state.entry = None
        state.exit_id = None
        state.exit_name = None
        if state.mode == "historic":
            state.at = None
    elif step == Step.WEEKDAY:
        state.weekday = None
        state.entry = None
        state.exit_id = None
        state.exit_name = None
    elif step == Step.ENTRY:
        state.entry = None
        state.exit_id = None
        state.exit_name = None
    elif step == Step.EXIT:
        state.exit_id = None
        state.exit_name = None
    elif step == Step.DATETIME:
        state.at = None


def _prefill_value(state: WizardState, step: Step):
    if step == Step.MODE:
        return state.mode
    if step == Step.DIRECTION:
        return state.direction
    if step == Step.WEEKDAY:
        return state.weekday
    if step == Step.ENTRY:
        return state.entry.id if state.entry else None
    if step == Step.EXIT:
        return state.exit_id
    if step == Step.DATETIME:
        return state.at
    return None


def _apply_current_mode(state: WizardState) -> None:
    now = datetime.now(EASTERN)
    direction = active_direction(now)
    if direction is None:
        typer.echo("There are no tolls right now.")
        raise typer.Exit(0)
    state.direction = direction
    state.at = now


def _run_step(state: WizardState, step: Step):
    if step == Step.MODE:
        result = prompts.select_mode(default=state.mode)
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        state.mode = result
        if result == "current":
            _apply_current_mode(state)
        return None

    if step == Step.DIRECTION:
        result = prompts.select_route_direction(default=state.direction)
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        state.direction = result
        return None

    if step == Step.WEEKDAY:
        result = prompts.select_weekday(default=state.weekday)
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        state.weekday = result
        return None

    if step == Step.ENTRY:
        if state.direction is None:
            raise RuntimeError("direction must be set before entry selection")
        entries = _entries_for_direction(state.direction == "eastbound")
        options = [(entry.id, entry.name) for entry in entries]
        result = prompts.select_interchange(
            "Entry", options, default_id=_prefill_value(state, step)
        )
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        entry_id, entry_name = result
        state.entry = Interchange(
            id=entry_id, name=entry_name, direction=state.direction
        )
        return None

    if step == Step.EXIT:
        if state.entry is None:
            raise RuntimeError("entry must be set before exit selection")
        result = prompts.select_interchange(
            "Exit",
            list_exits(state.entry),
            default_id=_prefill_value(state, step),
        )
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        state.exit_id, state.exit_name = result
        return None

    if step == Step.DATETIME:
        result = prompts.prompt_datetime(default=state.at)
        if result is Quit:
            return Quit
        if result is GoBack:
            return GoBack
        state.at = result.replace(tzinfo=EASTERN)
        return None

    raise RuntimeError(f"unknown step: {step}")


def is_complete(state: WizardState) -> bool:
    if state.mode is None or state.entry is None or state.exit_id is None:
        return False
    if state.mode == "current":
        return state.direction is not None and state.at is not None
    if state.mode == "chart":
        return state.direction is not None and state.weekday is not None
    if state.mode == "historic":
        return state.direction is not None and state.at is not None
    return False


def _step_done(state: WizardState, step: Step) -> bool:
    if step == Step.MODE:
        return state.mode is not None
    if step == Step.DIRECTION:
        return state.direction is not None
    if step == Step.WEEKDAY:
        return state.weekday is not None
    if step == Step.ENTRY:
        return state.entry is not None
    if step == Step.EXIT:
        return state.exit_id is not None
    if step == Step.DATETIME:
        return state.at is not None
    return True


def _should_skip_step(state: WizardState, step: Step) -> bool:
    if step not in state.skip_prompt:
        return False
    return _step_done(state, step)


def _next_pending_step(state: WizardState) -> Optional[Step]:
    for step in compute_steps(state):
        if not _step_done(state, step):
            return step
    return None


def run_wizard(state: WizardState) -> WizardState:
    while True:
        steps = compute_steps(state)
        step = _next_pending_step(state)
        if step is None:
            break

        if _should_skip_step(state, step):
            if (
                step == Step.MODE
                and state.mode == "current"
                and state.direction is None
            ):
                _apply_current_mode(state)
            state.skip_prompt.discard(step)
            continue

        result = _run_step(state, step)
        if result is Quit:
            raise typer.Exit(0)
        if result is GoBack:
            step_index = steps.index(step)
            if step_index == 0:
                continue
            previous = steps[step_index - 1]
            _clear_from(state, previous)
            state.skip_prompt.discard(previous)
            continue

        state.skip_prompt.discard(step)

    return state


def show_result(state: WizardState) -> None:
    if state.entry is None or state.exit_id is None or state.direction is None:
        raise RuntimeError("incomplete wizard state")
    if state.mode == "historic" and state.at is None:
        raise RuntimeError(
            "incomplete wizard state: historic lookup requires a date/time"
        )

    at = state.at if state.at is not None else datetime.now(EASTERN)
    if state.mode == "current" and not toll_window_active(at, state.direction):
        typer.echo("There is no current toll for this route right now.")
        return

    amount = get_toll(
        state.entry,
        state.exit_id,
        at=at,
        is_current=state.mode == "current",
    )
    label = _direction_label(state.direction)
    when_label = at.strftime("%m/%d/%Y %I:%M %p") if state.mode == "historic" else "now"
    if amount is None:
        typer.echo(
            f"{label}: {state.entry.name} → {state.exit_name}: Data Not Available ({when_label})"
        )
        return
    typer.echo(
        f"{label}: {state.entry.name} → {state.exit_name}: ${amount:.2f} ({when_label})"
    )


def show_chart_result(state: WizardState) -> None:
    if (
        state.entry is None
        or state.exit_id is None
        or state.direction is None
        or state.weekday is None
    ):
        raise RuntimeError("incomplete wizard state")

    trends = fetch_price_trends()
    begin_zone, end_zone = get_route_zones(state.entry, state.exit_id)
    times, prices = trends.series(
        state.direction,
        state.weekday,
        begin_zone,
        end_zone,
    )
    show_price_chart(
        weekday=state.weekday,
        entry_name=state.entry.name,
        exit_name=state.exit_name or str(state.exit_id),
        times=times,
        prices=prices,
        week_count=trends.week_count,
    )


def _direction_label(direction: Direction) -> str:
    return EASTBOUND_LABEL if direction == "eastbound" else WESTBOUND_LABEL


def run(state: WizardState) -> None:
    if is_complete(state):
        if state.mode == "chart":
            show_chart_result(state)
        else:
            show_result(state)
        return

    if not sys.stdin.isatty():
        typer.echo("error: incomplete arguments for non-interactive use", err=True)
        raise typer.Exit(1)

    try:
        state = run_wizard(state)
    except KeyboardInterrupt:
        raise typer.Exit(130) from None
    if not is_complete(state):
        typer.echo("error: lookup cancelled or incomplete", err=True)
        raise typer.Exit(1)
    if state.mode == "chart":
        show_chart_result(state)
    else:
        show_result(state)
