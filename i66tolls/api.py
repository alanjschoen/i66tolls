"""Client for the VDOT I-66 toll calculator API (vai66tolls.com)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Optional
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://vai66tolls.com/Index"
EASTERN = ZoneInfo("US/Eastern")
OPTION_RE = re.compile(r'<option value="(\d+)">([^<]+)</option>')
RUN_CHART_RE = re.compile(r"runChartMake\(\d+,(\d+),(\d+),")
# Exit(name, x, y, dir, id, lat, lng, enterZoneId, ...)
EXIT_CTOR_RE = re.compile(
    r"new Exit\("
    r"'([^']+)',\s*"
    r"[^,]+,\s*"
    r"[^,]+,\s*"
    r"'([^']+)',\s*"
    r"(\d+),\s*"
    r"[^,]+,\s*"
    r"[^,]+,\s*"
    r"(\d+)"
)

Direction = Literal["eastbound", "westbound"]

FetchFn = Callable[[str, dict[str, str]], str]
_active_fetch: Optional[FetchFn] = None


@dataclass(frozen=True)
class Interchange:
    id: int
    name: str
    direction: Direction
    zone: Optional[int] = None


def set_active_fetch(fetch: Optional[FetchFn]) -> None:
    global _active_fetch
    _active_fetch = fetch


def _fetch(handler: str, params: dict[str, str]) -> str:
    if _active_fetch is not None:
        return _active_fetch(handler, params)
    query = urlencode({"handler": handler, **params})
    with urlopen(f"{BASE_URL}?{query}", timeout=30) as response:
        return response.read().decode()


def _parse_options(html: str) -> list[tuple[int, str]]:
    return [(int(match[0]), match[1].strip()) for match in OPTION_RE.findall(html)]


def _parse_entries(html: str, direction: Direction) -> list[Interchange]:
    expected_dir = "eb" if direction == "eastbound" else "wb"
    from_ctors = [
        Interchange(
            id=int(match.group(3)),
            name=match.group(1),
            direction=direction,
            zone=int(match.group(4)) - 1,
        )
        for match in EXIT_CTOR_RE.finditer(html)
        if match.group(2) == expected_dir
    ]
    if from_ctors:
        return from_ctors
    return [
        Interchange(id=id_, name=name, direction=direction)
        for id_, name in _parse_options(html)
    ]


def _entries_for_direction(eastbound: bool) -> list[Interchange]:
    direction: Direction = "eastbound" if eastbound else "westbound"
    html = _fetch("BeginIntPartial", {"rbEastVal": "true" if eastbound else "false"})
    return _parse_entries(html, direction)


def list_entries() -> list[Interchange]:
    return _entries_for_direction(True) + _entries_for_direction(False)


def list_exits(entry: Interchange) -> list[tuple[int, str]]:
    eastbound = entry.direction == "eastbound"
    html = _fetch(
        "ExitIntPartial",
        {"bIntId": str(entry.id), "rbEastVal": "true" if eastbound else "false"},
    )
    return _parse_options(html)


def _toll_calc_response(
    entry: Interchange,
    exit_id: int,
    *,
    at: Optional[datetime] = None,
    is_current: bool = True,
) -> dict[str, object]:
    when = at.astimezone(EASTERN) if at is not None else datetime.now(EASTERN)
    eastbound = entry.direction == "eastbound"
    body = _fetch(
        "TollCalcPartial",
        {
            "bIntId": str(entry.id),
            "eIntId": str(exit_id),
            "datePicked": when.strftime("%m/%d/%Y"),
            "timePicked": when.strftime("%I:%M %p"),
            "rbEastVal": "true" if eastbound else "false",
            "isCurrent": "true" if is_current else "false",
        },
    )
    return json.loads(body)


def _zones_from_response(response: dict[str, object]) -> tuple[int, int]:
    js_to_run = str(response["jsToRun"])
    match = RUN_CHART_RE.search(js_to_run)
    if match is None:
        raise ValueError("route zone data not available")
    return int(match.group(1)), int(match.group(2))


def _amount_from_response(response: dict[str, object]) -> Optional[float]:
    amount = float(response["decToll"])
    if amount == -1:
        return None
    return amount


def get_toll(
    entry: Interchange,
    exit_id: int,
    *,
    at: Optional[datetime] = None,
    is_current: bool = True,
) -> Optional[float]:
    return _amount_from_response(
        _toll_calc_response(entry, exit_id, at=at, is_current=is_current)
    )


def get_route_zones(
    entry: Interchange,
    exit_id: int,
    *,
    at: Optional[datetime] = None,
) -> tuple[int, int]:
    response = _toll_calc_response(entry, exit_id, at=at, is_current=False)
    return _zones_from_response(response)


def get_zone_prices(
    direction: Direction,
    *,
    at: Optional[datetime] = None,
    is_current: bool = True,
) -> tuple[Optional[float], ...]:
    """Return the per-zone toll for each pricing zone in ``direction``.

    Eastbound zones are 0–3; westbound zones are 4–7. Each value is the toll for
    a single-zone entry→exit pair covering that zone, or ``None`` when the
    calculator has no data.
    """
    entries = _entries_for_direction(direction == "eastbound")
    zones = sorted({entry.zone for entry in entries if entry.zone is not None})
    if not zones:
        raise ValueError("entry zone data not available")

    prices: list[Optional[float]] = []
    for zone in zones:
        price: Optional[float] = None
        found = False
        for entry in entries:
            if entry.zone != zone:
                continue
            for exit_id, _ in list_exits(entry):
                response = _toll_calc_response(
                    entry, exit_id, at=at, is_current=is_current
                )
                begin, end = _zones_from_response(response)
                if begin == end == zone:
                    price = _amount_from_response(response)
                    found = True
                    break
            if found:
                break
        if not found:
            raise ValueError(f"no single-zone route found for zone {zone}")
        prices.append(price)
    return tuple(prices)


def infer_direction(entry_id: int, exit_id: int) -> Direction:
    matches: list[Direction] = []
    for eastbound in (True, False):
        entries = _entries_for_direction(eastbound)
        entry_matches = [entry for entry in entries if entry.id == entry_id]
        if not entry_matches:
            continue
        entry = entry_matches[0]
        if any(option_id == exit_id for option_id, _ in list_exits(entry)):
            matches.append(entry.direction)

    if not matches:
        raise ValueError(f"No route found for entry {entry_id} and exit {exit_id}")

    if len(matches) > 1:
        raise ValueError(
            f"Entry {entry_id} and exit {exit_id} are ambiguous across directions"
        )

    return matches[0]


def lookup_entry(entry_id: int, direction: Direction) -> Interchange:
    entries = _entries_for_direction(direction == "eastbound")
    for entry in entries:
        if entry.id == entry_id:
            return entry
    raise ValueError(f"Entry {entry_id} not found for {direction}")
