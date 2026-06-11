"""Command-line interface for I-66 toll lookups."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import typer

from i66tolls.wizard import build_initial_state, run

EASTERN = ZoneInfo("US/Eastern")


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    try:
        parsed = datetime.strptime(value, "%m/%d/%Y %I:%M %p")
    except ValueError as error:
        raise typer.BadParameter(
            "use MM/DD/YYYY HH:MM AM/PM, e.g. 06/10/2026 08:00 AM",
        ) from error
    return parsed.replace(tzinfo=EASTERN)


def main(
    entry: Optional[int] = typer.Argument(None, help="entry interchange ID"),
    exit: Optional[int] = typer.Argument(None, help="exit interchange ID"),
    time: Optional[str] = typer.Option(
        None,
        "-t",
        "--time",
        help="historic date/time (MM/DD/YYYY HH:MM AM/PM, US/Eastern)",
    ),
    eastbound: bool = typer.Option(False, "-e", "--eastbound", help="eastbound route"),
    westbound: bool = typer.Option(False, "-w", "--westbound", help="westbound route"),
    current: bool = typer.Option(False, "-c", "--current", help="use the current toll rate"),
) -> None:
    """Look up I-66 inside-the-Beltway tolls."""
    if eastbound and westbound:
        typer.echo("error: --eastbound and --westbound cannot be used together", err=True)
        raise typer.Exit(1)

    if current and time is not None:
        typer.echo("error: --current and --time cannot be used together", err=True)
        raise typer.Exit(1)

    if (entry is None) != (exit is None):
        typer.echo("error: provide both entry and exit IDs, or neither", err=True)
        raise typer.Exit(1)

    direction = None
    if eastbound:
        direction = "eastbound"
    elif westbound:
        direction = "westbound"

    direction_choice = None
    when = None
    if current:
        when = "current"
        if direction is not None:
            direction_choice = direction
        elif entry is not None and exit is not None:
            direction_choice = "current"
        else:
            direction_choice = "current"
    elif time is not None:
        when = "historic"

    try:
        state = build_initial_state(
            entry_id=entry,
            exit_id=exit,
            at=_parse_time(time),
            direction=direction,
            direction_choice=direction_choice,
            when=when,
        )
    except typer.BadParameter:
        raise
    except ValueError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error

    run(state)


def main_entry() -> None:
    typer.run(main)


if __name__ == "__main__":
    main_entry()
