"""Price trend data embedded in the vai66tolls.com homepage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.request import urlopen

HOMEPAGE_URL = "https://vai66tolls.com/"
DATA_PUSH_RE = re.compile(
    r"(?P<array>ewdv|wwdv)\[(?P<day>\d+)\]\[(?P<begin>\d+)\]\[(?P<end>\d+)\]"
    r"\.push\((?P<value>[-\d.]+)\)"
)
TIME_PUSH_RE = re.compile(r"(?P<array>etNames|wtNames)\.push\('(?P<label>[^']+)'\)")
WEEK_COUNT_RE = re.compile(r"var weekCount = (\d+);")

Direction = Literal["eastbound", "westbound"]
WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

# 15-minute sample grids used by vai66tolls.com during toll windows.
EASTBOUND_SAMPLE_TIMES: tuple[str, ...] = (
    "05:30 AM",
    "05:45 AM",
    "06:00 AM",
    "06:15 AM",
    "06:30 AM",
    "06:45 AM",
    "07:00 AM",
    "07:15 AM",
    "07:30 AM",
    "07:45 AM",
    "08:00 AM",
    "08:15 AM",
    "08:30 AM",
    "08:45 AM",
    "09:00 AM",
    "09:15 AM",
)
WESTBOUND_SAMPLE_TIMES: tuple[str, ...] = (
    "03:00 PM",
    "03:15 PM",
    "03:30 PM",
    "03:45 PM",
    "04:00 PM",
    "04:15 PM",
    "04:30 PM",
    "04:45 PM",
    "05:00 PM",
    "05:15 PM",
    "05:30 PM",
    "05:45 PM",
    "06:00 PM",
    "06:15 PM",
    "06:30 PM",
    "06:45 PM",
)

_cached_trends: Optional["PriceTrends"] = None


@dataclass(frozen=True)
class PriceTrends:
    week_count: int
    eastbound_times: tuple[str, ...]
    westbound_times: tuple[str, ...]
    eastbound: dict[int, dict[tuple[int, int], tuple[float, ...]]] = field(
        repr=False, default_factory=dict
    )
    westbound: dict[int, dict[tuple[int, int], tuple[float, ...]]] = field(
        repr=False, default_factory=dict
    )

    def series(
        self,
        direction: Direction,
        weekday: int,
        begin_zone: int,
        end_zone: int,
    ) -> tuple[tuple[str, ...], tuple[float, ...]]:
        if weekday < 0 or weekday > 4:
            raise ValueError(f"weekday must be 0-4, got {weekday}")
        by_direction = self.eastbound if direction == "eastbound" else self.westbound
        by_weekday = by_direction.get(weekday)
        if by_weekday is None:
            raise ValueError(f"no trend data for weekday {weekday}")
        values = by_weekday.get((begin_zone, end_zone))
        if values is None:
            raise ValueError(
                f"no trend data for zones {begin_zone}->{end_zone} on "
                f"{WEEKDAY_NAMES[weekday]}"
            )
        times = self.eastbound_times if direction == "eastbound" else self.westbound_times
        return times, values


def _fetch_homepage() -> str:
    with urlopen(HOMEPAGE_URL, timeout=30) as response:
        return response.read().decode()


def parse_price_trends(html: str) -> PriceTrends:
    week_count_match = WEEK_COUNT_RE.search(html)
    if week_count_match is None:
        raise ValueError("weekCount not found in homepage HTML")

    eastbound_times = tuple(
        match.group("label") for match in TIME_PUSH_RE.finditer(html) if match.group("array") == "etNames"
    )
    westbound_times = tuple(
        match.group("label") for match in TIME_PUSH_RE.finditer(html) if match.group("array") == "wtNames"
    )
    if not eastbound_times or not westbound_times:
        raise ValueError("time labels not found in homepage HTML")

    raw: dict[str, dict[int, dict[tuple[int, int], list[float]]]] = {
        "ewdv": {},
        "wwdv": {},
    }
    for match in DATA_PUSH_RE.finditer(html):
        array = match.group("array")
        day = int(match.group("day"))
        begin = int(match.group("begin"))
        end = int(match.group("end"))
        value = float(match.group("value"))
        raw[array].setdefault(day, {}).setdefault((begin, end), []).append(value)

    eastbound = {
        day: {zones: tuple(values) for zones, values in zone_map.items()}
        for day, zone_map in raw["ewdv"].items()
    }
    westbound = {
        day: {zones: tuple(values) for zones, values in zone_map.items()}
        for day, zone_map in raw["wwdv"].items()
    }
    return PriceTrends(
        week_count=int(week_count_match.group(1)),
        eastbound_times=eastbound_times,
        westbound_times=westbound_times,
        eastbound=eastbound,
        westbound=westbound,
    )


def fetch_price_trends(*, force_refresh: bool = False) -> PriceTrends:
    global _cached_trends
    if _cached_trends is not None and not force_refresh:
        return _cached_trends
    trends = parse_price_trends(_fetch_homepage())
    _cached_trends = trends
    return trends
