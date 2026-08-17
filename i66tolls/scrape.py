"""Historical toll price scraping."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn

from i66tolls.api import (
    EASTERN,
    Direction,
    _amount_from_response,
    _toll_calc_response,
    set_active_fetch,
)
from i66tolls.client import RateLimitedClient
from i66tolls.period import scrape_date_range, weekdays_in_range
from i66tolls.storage import (
    DIRECTIONS,
    SCHEMA_VERSION,
    DirectionRecord,
    SampleRecord,
    default_data_dir,
    direction_path,
    is_day_complete,
    is_direction_complete,
    missing_dates,
    new_scraped_at,
    save_direction,
)
from i66tolls.trends import EASTBOUND_SAMPLE_TIMES, WESTBOUND_SAMPLE_TIMES
from i66tolls.zones import ZoneProbe, clear_probe_cache, resolve_zone_probes

SAMPLE_TIMES: dict[Direction, tuple[str, ...]] = {
    "eastbound": EASTBOUND_SAMPLE_TIMES,
    "westbound": WESTBOUND_SAMPLE_TIMES,
}

StepCallback = Callable[[str], None]


@dataclass
class ScrapeSummary:
    period: str
    data_dir: Path
    start: date
    end: date
    planned: list[date]
    fetched: list[date]
    partial: list[date]
    failed: list[date]
    skipped: list[date]

    @property
    def attempted(self) -> int:
        return len(self.fetched) + len(self.partial) + len(self.failed)

    @property
    def succeeded(self) -> bool:
        return bool(self.fetched or self.partial)


def _count_scrape_steps(
    data_dir: Path,
    days: list[date],
    probes_by_direction: dict[Direction, tuple[ZoneProbe, ...]],
) -> int:
    total = 0
    for day in days:
        for direction in DIRECTIONS:
            if is_direction_complete(direction_path(data_dir, day, direction), direction):
                continue
            total += len(SAMPLE_TIMES[direction]) * len(probes_by_direction[direction])
    return total


def _parse_sample_time(day: date, time_label: str) -> datetime:
    parsed = datetime.strptime(
        f"{day.isoformat()} {time_label}",
        "%Y-%m-%d %I:%M %p",
    )
    return parsed.replace(tzinfo=EASTERN)


def _sample_zone_price(
    probe: ZoneProbe,
    *,
    at: datetime,
) -> Optional[float]:
    response = _toll_calc_response(
        probe.entry,
        probe.exit_id,
        at=at,
        is_current=False,
    )
    return _amount_from_response(response)


def scrape_direction(
    data_dir: Path,
    day: date,
    direction: Direction,
    probes: tuple[ZoneProbe, ...],
    *,
    scraped_at: Optional[str] = None,
    on_step: Optional[StepCallback] = None,
) -> DirectionRecord:
    samples: list[SampleRecord] = []
    for time_label in SAMPLE_TIMES[direction]:
        zones: list[Optional[float]] = []
        errors: list[str] = []
        at = _parse_sample_time(day, time_label)
        for probe in probes:
            if on_step is not None:
                on_step(f"{day.isoformat()} {direction} {time_label}")
            try:
                zones.append(_sample_zone_price(probe, at=at))
            except BaseException as error:
                zones.append(None)
                errors.append(f"zone {probe.zone}: {error}")
        samples.append(SampleRecord(time=time_label, zones=zones, errors=errors))

    return DirectionRecord(
        schema_version=SCHEMA_VERSION,
        date=day.isoformat(),
        direction=direction,
        scraped_at=scraped_at or new_scraped_at(),
        samples=samples,
    )


def scrape_day(
    data_dir: Path,
    day: date,
    probes_by_direction: dict[Direction, tuple[ZoneProbe, ...]],
    *,
    on_step: Optional[StepCallback] = None,
) -> tuple[bool, bool]:
    """Scrape one day. Returns ``(saved_any, complete)``."""
    scraped_at = new_scraped_at()
    saved_any = False
    for direction in DIRECTIONS:
        path = direction_path(data_dir, day, direction)
        if is_direction_complete(path, direction):
            continue
        record = scrape_direction(
            data_dir,
            day,
            direction,
            probes_by_direction[direction],
            scraped_at=scraped_at,
            on_step=on_step,
        )
        save_direction(data_dir, record)
        saved_any = True
    return saved_any, is_day_complete(data_dir, day)


def run_scrape(
    period: str,
    *,
    data_dir: Optional[Path] = None,
    delay: float = 0.1,
    jitter: float = 0.2,
    max_retries: int = 3,
    dry_run: bool = False,
    show_progress: Optional[bool] = None,
    now: Optional[datetime] = None,
) -> ScrapeSummary:
    root = data_dir or default_data_dir()
    start, end = scrape_date_range(period, now=now)
    planned = missing_dates(root, start, end)
    all_weekdays = weekdays_in_range(start, end)
    skipped = [day for day in all_weekdays if day not in planned]

    summary = ScrapeSummary(
        period=period,
        data_dir=root,
        start=start,
        end=end,
        planned=planned,
        fetched=[],
        partial=[],
        failed=[],
        skipped=skipped,
    )

    if dry_run:
        return summary

    use_progress = sys.stderr.isatty() if show_progress is None else show_progress

    client = RateLimitedClient(delay=delay, jitter=jitter, max_retries=max_retries)
    set_active_fetch(client.fetch)
    clear_probe_cache()

    try:
        probes_by_direction: dict[Direction, tuple[ZoneProbe, ...]] = {}
        for direction in DIRECTIONS:
            probes_by_direction[direction] = resolve_zone_probes(direction)

        total_steps = _count_scrape_steps(root, planned, probes_by_direction)
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            disable=not use_progress or total_steps == 0,
        )
        with progress:
            task_id = progress.add_task("scraping", total=total_steps)

            def on_step(description: str) -> None:
                progress.update(task_id, description=description)
                progress.advance(task_id)

            for day in planned:
                try:
                    saved_any, complete = scrape_day(
                        root,
                        day,
                        probes_by_direction,
                        on_step=on_step if total_steps else None,
                    )
                    if not saved_any:
                        continue
                    if complete:
                        summary.fetched.append(day)
                    else:
                        summary.partial.append(day)
                except BaseException as error:
                    print(f"failed {day.isoformat()}: {error}", file=sys.stderr)
                    summary.failed.append(day)
    finally:
        set_active_fetch(None)
        clear_probe_cache()

    return summary


def format_summary(summary: ScrapeSummary) -> str:
    lines = [
        f"period: {summary.period}",
        f"range: {summary.start.isoformat()} .. {summary.end.isoformat()}",
        f"data dir: {summary.data_dir}",
        f"planned: {len(summary.planned)}",
        f"skipped (complete): {len(summary.skipped)}",
        f"fetched: {len(summary.fetched)}",
        f"partial: {len(summary.partial)}",
        f"failed: {len(summary.failed)}",
    ]
    if summary.planned:
        lines.append("dates to fetch: " + ", ".join(day.isoformat() for day in summary.planned))
    return "\n".join(lines)
