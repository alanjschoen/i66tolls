"""Client for the VDOT I-66 toll calculator API (vai66tolls.com)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

BASE_URL = "https://vai66tolls.com/Index"
EASTERN = ZoneInfo("US/Eastern")
OPTION_RE = re.compile(r'<option value="(\d+)">([^<]+)</option>')

Direction = Literal["eastbound", "westbound"]


@dataclass(frozen=True)
class Interchange:
    id: int
    name: str
    direction: Direction


def _fetch(handler: str, params: dict[str, str]) -> str:
    query = urlencode({"handler": handler, **params})
    with urlopen(f"{BASE_URL}?{query}", timeout=30) as response:
        return response.read().decode()


def _parse_options(html: str) -> list[tuple[int, str]]:
    return [(int(match[0]), match[1].strip()) for match in OPTION_RE.findall(html)]


def _entries_for_direction(eastbound: bool) -> list[Interchange]:
    direction: Direction = "eastbound" if eastbound else "westbound"
    html = _fetch("BeginIntPartial", {"rbEastVal": "true" if eastbound else "false"})
    return [Interchange(id=id_, name=name, direction=direction) for id_, name in _parse_options(html)]


def list_entries() -> list[Interchange]:
    return _entries_for_direction(True) + _entries_for_direction(False)


def list_exits(entry: Interchange) -> list[tuple[int, str]]:
    eastbound = entry.direction == "eastbound"
    html = _fetch(
        "ExitIntPartial",
        {"bIntId": str(entry.id), "rbEastVal": "true" if eastbound else "false"},
    )
    return _parse_options(html)


def get_toll(
    entry: Interchange,
    exit_id: int,
    *,
    at: Optional[datetime] = None,
    is_current: bool = True,
) -> float:
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
    return float(json.loads(body)["decToll"])


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
        raise ValueError(f"Entry {entry_id} and exit {exit_id} are ambiguous across directions")

    return matches[0]


def lookup_entry(entry_id: int, direction: Direction) -> Interchange:
    entries = _entries_for_direction(direction == "eastbound")
    for entry in entries:
        if entry.id == entry_id:
            return entry
    raise ValueError(f"Entry {entry_id} not found for {direction}")
