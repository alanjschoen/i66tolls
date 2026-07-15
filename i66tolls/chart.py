"""Terminal chart rendering for price trends."""

from __future__ import annotations

from typing import Sequence

import plotext as plt
import typer

from i66tolls.trends import WEEKDAY_NAMES


def show_price_chart(
    *,
    weekday: int,
    entry_name: str,
    exit_name: str,
    times: Sequence[str],
    prices: Sequence[float],
    week_count: int,
) -> None:
    day_name = WEEKDAY_NAMES[weekday]
    typer.echo(
        f"{week_count}-Week Average on {day_name}s — {entry_name} → {exit_name}"
    )
    plt.clf()
    plt.plot(
        list(range(len(times))),
        list(prices),
        label="Average toll ($)",
        marker="braille",
    )
    plt.xticks(list(range(len(times))), list(times))
    plt.ylim(0, max(prices) if prices else 1)
    plt.xlabel("Time")
    plt.ylabel("Toll ($)")
    plt.title(f"{day_name}s")
    plt.plotsize(100, 24)
    plt.show()
