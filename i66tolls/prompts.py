"""Interactive prompts with arrow-key navigation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, TypeVar, Union

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from i66tolls.hours import EASTBOUND_LABEL, WESTBOUND_LABEL

T = TypeVar("T")


class GoBack(Exception):
    """Raised when the user presses left arrow to return to the previous step."""


def _run_select(message: str, choices: list[Choice], default: Optional[Choice] = None) -> Union[T, type[GoBack]]:
    prompt = inquirer.select(
        message=message,
        choices=choices,
        default=default,
        instruction="(← back, ↵ select)",
        cycle=False,
    )

    @prompt.register_kb("left")
    def go_back(event) -> None:
        event.app.exit(exception=GoBack())

    try:
        return prompt.execute()
    except GoBack:
        return GoBack


def select_direction(
    *,
    default: Optional[str] = None,
) -> Union[str, type[GoBack]]:
    choices = [
        Choice("current", "current"),
        Choice("eastbound", EASTBOUND_LABEL),
        Choice("westbound", WESTBOUND_LABEL),
    ]
    default_choice = next((choice for choice in choices if choice.value == default), None)
    return _run_select("Direction", choices, default_choice)


def select_interchange(
    message: str,
    options: list[tuple[int, str]],
    *,
    default_id: Optional[int] = None,
) -> Union[tuple[int, str], type[GoBack]]:
    choices = [Choice((id_, name), f"{id_:>2}  {name}") for id_, name in options]
    default_choice = next((choice for choice in choices if choice.value[0] == default_id), None)
    return _run_select(message, choices, default_choice)


def select_when(*, default: Optional[str] = None) -> Union[str, type[GoBack]]:
    choices = [Choice("current", "current"), Choice("historic", "historic")]
    default_choice = next((choice for choice in choices if choice.value == default), None)
    return _run_select("When", choices, default_choice)


def prompt_datetime(*, default: Optional[datetime] = None) -> Union[datetime, type[GoBack]]:
    default_text = default.strftime("%m/%d/%Y %I:%M %p") if default else ""
    prompt = inquirer.text(
        message="Date and time (MM/DD/YYYY HH:MM AM/PM)",
        default=default_text,
        instruction="(← back, ↵ confirm)",
        validate=_validate_datetime_text,
        invalid_message="Use MM/DD/YYYY HH:MM AM/PM in US/Eastern time",
    )

    @prompt.register_kb("left")
    def go_back(event) -> None:
        event.app.exit(exception=GoBack())

    try:
        text = prompt.execute()
    except GoBack:
        return GoBack

    return datetime.strptime(text, "%m/%d/%Y %I:%M %p")


def _validate_datetime_text(text: str) -> bool:
    try:
        parsed = datetime.strptime(text, "%m/%d/%Y %I:%M %p")
    except ValueError:
        return False
    from zoneinfo import ZoneInfo

    eastern = ZoneInfo("US/Eastern")
    return parsed <= datetime.now(eastern).replace(tzinfo=None)
