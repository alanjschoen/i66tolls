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


@dataclass(frozen=True)
class Interchange:
    id: int
    name: str
    direction: Literal["eastbound", "westbound"]


def _fetch(handler: str, params: dict[str, str]) -> str:
    query = urlencode({"handler": handler, **params})
    with urlopen(f"{BASE_URL}?{query}", timeout=30) as response:
        return response.read().decode()


def _parse_options(html: str) -> list[tuple[int, str]]:
    return [(int(match[0]), match[1].strip()) for match in OPTION_RE.findall(html)]


def _entries_for_direction(eastbound: bool) -> list[Interchange]:
    direction: Literal["eastbound", "westbound"] = "eastbound" if eastbound else "westbound"
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


def _current_toll_time() -> tuple[str, str]:
    now = datetime.now(EASTERN)
    return now.strftime("%m/%d/%Y"), now.strftime("%I:%M %p")


def get_toll(entry: Interchange, exit_id: int) -> float:
    date_picked, time_picked = _current_toll_time()
    eastbound = entry.direction == "eastbound"
    body = _fetch(
        "TollCalcPartial",
        {
            "bIntId": str(entry.id),
            "eIntId": str(exit_id),
            "datePicked": date_picked,
            "timePicked": time_picked,
            "rbEastVal": "true" if eastbound else "false",
            "isCurrent": "true",
        },
    )
    return float(json.loads(body)["decToll"])


def resolve_entry(
    query: str,
    direction: Optional[Literal["eastbound", "westbound"]] = None,
) -> Interchange:
    entries = list_entries()
    if direction is not None:
        entries = [entry for entry in entries if entry.direction == direction]

    if query.isdigit():
        matches = [entry for entry in entries if entry.id == int(query)]
    else:
        needle = query.casefold()
        matches = [entry for entry in entries if needle in entry.name.casefold()]

    if not matches:
        raise ValueError(f"No entry matching {query!r}")

    if len(matches) > 1:
        lines = "\n".join(f"  {entry.id:>2}  {entry.name} ({entry.direction})" for entry in matches)
        raise ValueError(f"Multiple entries match {query!r}:\n{lines}")

    return matches[0]


def resolve_exit(entry: Interchange, query: str) -> tuple[int, str]:
    exits = list_exits(entry)
    if query.isdigit():
        matches = [(id_, name) for id_, name in exits if id_ == int(query)]
    else:
        needle = query.casefold()
        matches = [(id_, name) for id_, name in exits if needle in name.casefold()]

    if not matches:
        raise ValueError(f"No exit matching {query!r} for entry {entry.name}")

    if len(matches) > 1:
        lines = "\n".join(f"  {id_:>2}  {name}" for id_, name in matches)
        raise ValueError(f"Multiple exits match {query!r}:\n{lines}")

    return matches[0]
