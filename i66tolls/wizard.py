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
    get_toll,
    infer_direction,
    list_exits,
    lookup_entry,
)
from i66tolls.hours import EASTBOUND_LABEL, WESTBOUND_LABEL, active_direction, toll_window_active
from i66tolls.prompts import GoBack

EASTERN = ZoneInfo("US/Eastern")
Direction = Literal["eastbound", "westbound"]
DirectionChoice = Literal["current", "eastbound", "westbound"]


class Step(Enum):
    DIRECTION = auto()
    ENTRY = auto()
    EXIT = auto()
    WHEN = auto()
    DATETIME = auto()


@dataclass
class WizardState:
    direction_choice: Optional[DirectionChoice] = None
    direction: Optional[Direction] = None
    entry: Optional[Interchange] = None
    exit_id: Optional[int] = None
    exit_name: Optional[str] = None
    when: Optional[Literal["current", "historic"]] = None
    at: Optional[datetime] = None
    skip_prompt: set[Step] = field(default_factory=set)


def build_initial_state(
    *,
    entry_id: Optional[int],
    exit_id: Optional[int],
    at: Optional[datetime],
    direction: Optional[Direction],
    direction_choice: Optional[DirectionChoice],
    when: Optional[Literal["current", "historic"]],
) -> WizardState:
    state = WizardState()
    now = datetime.now(EASTERN)

    if direction is not None:
        state.direction = direction
        state.direction_choice = direction
        state.skip_prompt.add(Step.DIRECTION)

    if direction_choice == "current":
        state.direction_choice = "current"
        state.when = "current"
        state.at = now
        state.skip_prompt.add(Step.DIRECTION)
        state.skip_prompt.add(Step.WHEN)

    if when == "current":
        state.when = "current"
        state.at = now
        state.skip_prompt.add(Step.WHEN)
    elif when == "historic":
        state.when = "historic"
        state.skip_prompt.add(Step.WHEN)

    if at is not None:
        state.when = "historic"
        state.at = at.astimezone(EASTERN) if at.tzinfo else at.replace(tzinfo=EASTERN)
        state.skip_prompt.add(Step.WHEN)
        state.skip_prompt.add(Step.DATETIME)

    if entry_id is not None and exit_id is not None:
        inferred = infer_direction(entry_id, exit_id)
        state.direction = inferred
        if state.direction_choice is None:
            state.direction_choice = inferred
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
            raise ValueError("entry requires --eastbound/--westbound or an exit to infer direction")
        state.entry = lookup_entry(entry_id, state.direction)
        state.skip_prompt.add(Step.ENTRY)

    return state


def compute_steps(state: WizardState) -> list[Step]:
    steps = [Step.DIRECTION, Step.ENTRY, Step.EXIT]
    if state.direction_choice == "current":
        return steps
    if state.when is None:
        steps.append(Step.WHEN)
    if state.when == "historic" and state.at is None:
        steps.append(Step.DATETIME)
    return steps


def _clear_from(state: WizardState, step: Step) -> None:
    if step == Step.DIRECTION:
        state.direction_choice = None
        state.direction = None
        state.when = None
        state.at = None
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
    elif step == Step.WHEN:
        if state.direction_choice != "current":
            state.when = None
            state.at = None
    elif step == Step.DATETIME:
        state.at = None


def _prefill_value(state: WizardState, step: Step):
    if step == Step.DIRECTION:
        return state.direction_choice
    if step == Step.ENTRY:
        return state.entry.id if state.entry else None
    if step == Step.EXIT:
        return state.exit_id
    if step == Step.WHEN:
        return state.when
    if step == Step.DATETIME:
        return state.at
    return None


def _run_step(state: WizardState, step: Step):
    if step == Step.DIRECTION:
        result = prompts.select_direction(default=state.direction_choice)
        if result is GoBack:
            return GoBack
        return _apply_direction(state, result)

    if step == Step.ENTRY:
        if state.direction is None:
            raise RuntimeError("direction must be set before entry selection")
        entries = _entries_for_direction(state.direction == "eastbound")
        options = [(entry.id, entry.name) for entry in entries]
        result = prompts.select_interchange("Entry", options, default_id=_prefill_value(state, step))
        if result is GoBack:
            return GoBack
        entry_id, entry_name = result
        state.entry = Interchange(id=entry_id, name=entry_name, direction=state.direction)
        return None

    if step == Step.EXIT:
        if state.entry is None:
            raise RuntimeError("entry must be set before exit selection")
        result = prompts.select_interchange(
            "Exit",
            list_exits(state.entry),
            default_id=_prefill_value(state, step),
        )
        if result is GoBack:
            return GoBack
        state.exit_id, state.exit_name = result
        return None

    if step == Step.WHEN:
        result = prompts.select_when(default=state.when)
        if result is GoBack:
            return GoBack
        state.when = result
        if result == "current":
            state.at = datetime.now(EASTERN)
        else:
            state.at = None
        return None

    if step == Step.DATETIME:
        result = prompts.prompt_datetime(default=state.at)
        if result is GoBack:
            return GoBack
        state.at = result.replace(tzinfo=EASTERN)
        return None

    raise RuntimeError(f"unknown step: {step}")


def _apply_direction(state: WizardState, choice: DirectionChoice) -> None:
    state.direction_choice = choice
    if choice == "current":
        now = datetime.now(EASTERN)
        direction = active_direction(now)
        if direction is None:
            typer.echo("There are no tolls right now.")
            raise typer.Exit(0)
        state.direction = direction
        state.when = "current"
        state.at = now
        return

    state.direction = choice
    state.when = None
    state.at = None


def is_complete(state: WizardState) -> bool:
    if state.direction is None or state.entry is None or state.exit_id is None:
        return False
    if state.direction_choice == "current":
        return state.at is not None
    if state.when is None:
        return False
    if state.when == "current":
        return True
    return state.at is not None


def _step_done(state: WizardState, step: Step) -> bool:
    if step == Step.DIRECTION:
        if state.direction_choice == "current":
            return state.direction is not None
        return state.direction_choice is not None and state.direction is not None
    if step == Step.ENTRY:
        return state.entry is not None
    if step == Step.EXIT:
        return state.exit_id is not None
    if step == Step.WHEN:
        return state.when is not None
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
            if step == Step.DIRECTION and state.direction_choice == "current" and state.direction is None:
                _apply_direction(state, "current")
            state.skip_prompt.discard(step)
            continue

        result = _run_step(state, step)
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
    if state.when is None:
        raise RuntimeError("incomplete wizard state: when is unset")
    if state.when == "historic" and state.at is None:
        raise RuntimeError("incomplete wizard state: historic lookup requires a date/time")

    at = state.at if state.at is not None else datetime.now(EASTERN)
    if state.when == "current" and not toll_window_active(at, state.direction):
        typer.echo("There is no current toll for this route right now.")
        return

    amount = get_toll(
        state.entry,
        state.exit_id,
        at=at,
        is_current=state.when == "current",
    )
    label = _direction_label(state.direction)
    when_label = at.strftime("%m/%d/%Y %I:%M %p") if state.when == "historic" else "now"
    if amount is None:
        typer.echo(f"{label}: {state.entry.name} → {state.exit_name}: Data Not Available ({when_label})")
        return
    typer.echo(f"{label}: {state.entry.name} → {state.exit_name}: ${amount:.2f} ({when_label})")


def _direction_label(direction: Direction) -> str:
    return EASTBOUND_LABEL if direction == "eastbound" else WESTBOUND_LABEL


def run(state: WizardState) -> None:
    if is_complete(state):
        show_result(state)
        return

    if not sys.stdin.isatty():
        typer.echo("error: incomplete arguments for non-interactive use", err=True)
        raise typer.Exit(1)

    state = run_wizard(state)
    if not is_complete(state):
        typer.echo("error: lookup cancelled or incomplete", err=True)
        raise typer.Exit(1)
    show_result(state)
