"""Interactive prompts with arrow-key navigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, Optional, TypeVar, Union
from zoneinfo import ZoneInfo

from its_a_dt import Bounds, GoBack as DtGoBack, pick_datetime
from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Window
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style

from i66tolls.hours import EASTBOUND_LABEL, WESTBOUND_LABEL

EASTERN = ZoneInfo("US/Eastern")
T = TypeVar("T")

STYLE = Style.from_dict(
    {
        "title": "bold",
        "focus": "bold reverse",
        "hint": "#666666",
    }
)


class GoBack(Exception):
    """Sentinel returned when the user presses left arrow to go back."""


@dataclass
class _ListState(Generic[T]):
    focus_index: int
    go_back: bool = False
    selected: Optional[T] = None


def _default_index(choices: list[tuple[T, str]], default: Optional[T]) -> int:
    if default is None:
        return 0
    for index, (value, _) in enumerate(choices):
        if value == default:
            return index
    return 0


def _pick_list(
    title: str,
    choices: list[tuple[T, str]],
    *,
    default: Optional[T] = None,
) -> Union[T, type[GoBack]]:
    if not choices:
        raise ValueError("choices must not be empty")

    state = _ListState(focus_index=_default_index(choices, default))

    def render() -> FormattedText:
        lines: list[tuple[str, str]] = [("class:title", f"{title}\n\n")]
        for index, (_, label) in enumerate(choices):
            prefix = "❯ " if index == state.focus_index else "  "
            if index == state.focus_index:
                lines.append(("class:focus", f"{prefix}{label}\n"))
            else:
                lines.append(("", f"{prefix}{label}\n"))
        lines.append(("", "\n"))
        lines.append(("class:hint", "  ← back  ↑↓ navigate  Enter select"))
        return FormattedText(lines)

    kb = KeyBindings()

    @kb.add("up")
    def move_up(event) -> None:
        if state.focus_index > 0:
            state.focus_index -= 1
        event.app.invalidate()

    @kb.add("down")
    def move_down(event) -> None:
        if state.focus_index < len(choices) - 1:
            state.focus_index += 1
        event.app.invalidate()

    @kb.add("left")
    def go_back(event) -> None:
        state.go_back = True
        event.app.exit()

    @kb.add("enter")
    def select(event) -> None:
        state.selected = choices[state.focus_index][0]
        event.app.exit()

    control = FormattedTextControl(lambda: render())
    window = Window(content=control, wrap_lines=False, always_hide_cursor=True)
    layout = Layout(HSplit([window]))
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        style=STYLE,
        mouse_support=False,
        erase_when_done=True,
    )
    with patch_stdout():
        app.run()

    if state.go_back:
        return GoBack
    if state.selected is None:
        raise RuntimeError("picker exited without a selection")
    return state.selected


def select_direction(
    *,
    default: Optional[str] = None,
) -> Union[str, type[GoBack]]:
    choices: list[tuple[str, str]] = [
        ("current", "current"),
        ("eastbound", EASTBOUND_LABEL),
        ("westbound", WESTBOUND_LABEL),
    ]
    return _pick_list("Direction", choices, default=default)


def select_interchange(
    message: str,
    options: list[tuple[int, str]],
    *,
    default_id: Optional[int] = None,
) -> Union[tuple[int, str], type[GoBack]]:
    choices = [((id_, name), f"{id_:>2}  {name}") for id_, name in options]
    default = next((choice for choice in choices if choice[0][0] == default_id), None)
    return _pick_list(message, choices, default=default)


def select_when(*, default: Optional[str] = None) -> Union[str, type[GoBack]]:
    choices = [("current", "current"), ("historic", "historic")]
    return _pick_list("When", choices, default=default)


def prompt_datetime(*, default: Optional[datetime] = None) -> Union[datetime, type[GoBack]]:
    now = datetime.now(EASTERN).replace(tzinfo=None)
    default_naive = None
    if default is not None:
        default_naive = default.astimezone(EASTERN).replace(tzinfo=None) if default.tzinfo else default

    result = pick_datetime(
        bounds=Bounds(max=now),
        default=default_naive,
        title="Historic date and time",
    )
    if result is DtGoBack:
        return GoBack
    return result
