"""Command-line interface for I-66 toll lookups."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import typer

from i66tolls.api import get_zone_prices
from i66tolls.hours import active_direction
from i66tolls.scrape import format_summary, run_scrape
from i66tolls.wizard import build_initial_state, run

EASTERN = ZoneInfo("US/Eastern")

# for python 3.10 compatibility
lookup_app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
scrape_app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Existing tests invoke the lookup CLI directly.
app = lookup_app


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


def _format_zone_prices(prices: tuple[Optional[float], ...]) -> str:
    parts = ["None" if price is None else f"{price:.2f}" for price in prices]
    return f"[{', '.join(parts)}]"


def show_state(*, at: Optional[datetime] = None) -> None:
    when = at.astimezone(EASTERN) if at is not None else datetime.now(EASTERN)
    typer.echo(when.strftime("%m/%d/%Y %I:%M %p"))
    direction = active_direction(when)
    if direction is None:
        return
    prices = get_zone_prices(direction, at=when, is_current=True)
    typer.echo(_format_zone_prices(prices))


@lookup_app.command()
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
    state: bool = typer.Option(
        False,
        "--state",
        help="print current time and per-zone prices (time only outside toll hours)",
    ),
) -> None:
    """Look up I-66 inside-the-Beltway tolls."""
    if state:
        if (
            entry is not None
            or exit is not None
            or time is not None
            or eastbound
            or westbound
            or current
        ):
            typer.echo("error: --state cannot be combined with other options", err=True)
            raise typer.Exit(1)
        try:
            show_state()
        except ValueError as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
        return

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

    mode = None
    if current:
        mode = "current"
    elif time is not None:
        mode = "historic"

    try:
        wizard_state = build_initial_state(
            entry_id=entry,
            exit_id=exit,
            at=_parse_time(time),
            direction=direction,
            mode=mode,
        )
    except typer.BadParameter:
        raise
    except ValueError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error

    run(wizard_state)


@scrape_app.command()
def scrape(
    period: str = typer.Argument(
        "1 week",
        help="Lookback period, e.g. 7d, 1 week, 2 weeks, 1 month",
    ),
    data_dir: Optional[Path] = typer.Option(
        None,
        "--data-dir",
        help="Override storage root",
    ),
    delay: float = typer.Option(0.1, "--delay", help="Base seconds between API calls"),
    jitter: float = typer.Option(
        0.2,
        "--jitter",
        help="Max random extra seconds added to each delay",
    ),
    max_retries: int = typer.Option(3, "--max-retries"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without fetching"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress bar"),
) -> None:
    """Download missing historical per-zone toll prices."""
    try:
        summary = run_scrape(
            period,
            data_dir=data_dir,
            delay=delay,
            jitter=jitter,
            max_retries=max_retries,
            dry_run=dry_run,
            show_progress=False if no_progress else None,
        )
    except ValueError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error

    typer.echo(format_summary(summary))
    if dry_run or summary.attempted == 0:
        return
    if not summary.succeeded:
        raise typer.Exit(1)


def main_entry() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "scrape":
        sys.argv.pop(1)
        scrape_app(prog_name="i66tolls scrape")
        return
    lookup_app(prog_name="i66tolls")


if __name__ == "__main__":
    main_entry()
