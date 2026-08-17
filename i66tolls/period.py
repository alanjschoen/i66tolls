"""Lookback period parsing and scrape date ranges."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("US/Eastern")

_PERIOD_RE = re.compile(
    r"^\s*(?:(\d+)\s*(d|day|days|w|week|weeks|m|month|months))\s*$",
    re.IGNORECASE,
)


def parse_period(text: str) -> timedelta:
    """Parse a lookback period such as ``7d``, ``1 week``, or ``2 months``."""
    normalized = text.strip().lower()
    match = _PERIOD_RE.match(normalized)
    if match is None:
        raise ValueError(
            f"invalid period {text!r}; use forms like 7d, 1 week, 2 weeks, 1 month"
        )
    amount = int(match.group(1))
    if amount <= 0:
        raise ValueError(f"period must be positive, got {amount}")
    unit = match.group(2).lower()
    if unit in ("d", "day", "days"):
        return timedelta(days=amount)
    if unit in ("w", "week", "weeks"):
        return timedelta(weeks=amount)
    return timedelta(days=amount * 30)


def today_eastern(*, now: Optional[datetime] = None) -> date:
    when = now.astimezone(EASTERN) if now is not None else datetime.now(EASTERN)
    return when.date()


def scrape_date_range(
    period: str,
    *,
    now: Optional[datetime] = None,
) -> tuple[date, date]:
    """Return inclusive ``[start, end]`` for scraping, ending yesterday."""
    today = today_eastern(now=now)
    end = today - timedelta(days=1)
    start = today - parse_period(period)
    if start > end:
        raise ValueError("period does not include any days before today")
    return start, end


def is_weekday(day: date) -> bool:
    return day.weekday() < 5


def weekdays_in_range(start: date, end: date) -> list[date]:
    if start > end:
        return []
    days: list[date] = []
    current = start
    while current <= end:
        if is_weekday(current):
            days.append(current)
        current += timedelta(days=1)
    return days
