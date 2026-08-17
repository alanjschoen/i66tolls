"""Zone probe resolution for toll scraping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from i66tolls.api import (
    Direction,
    Interchange,
    _amount_from_response,
    _entries_for_direction,
    _toll_calc_response,
    _zones_from_response,
    list_exits,
)

_probe_cache: dict[tuple[Direction, bool, bool], tuple["ZoneProbe", ...]] = {}


@dataclass(frozen=True)
class ZoneProbe:
    zone: int
    entry: Interchange
    exit_id: int


def clear_probe_cache() -> None:
    _probe_cache.clear()


def resolve_zone_probes(
    direction: Direction,
    *,
    at: Optional[datetime] = None,
    is_current: bool = True,
) -> tuple[ZoneProbe, ...]:
    cache_key = (direction, at is None, is_current)
    cached = _probe_cache.get(cache_key)
    if cached is not None:
        return cached

    entries = _entries_for_direction(direction == "eastbound")
    zones = sorted({entry.zone for entry in entries if entry.zone is not None})
    if not zones:
        raise ValueError("entry zone data not available")

    probes: list[ZoneProbe] = []
    for zone in zones:
        found = False
        for entry in entries:
            if entry.zone != zone:
                continue
            for exit_id, _ in list_exits(entry):
                response = _toll_calc_response(
                    entry,
                    exit_id,
                    at=at,
                    is_current=is_current,
                )
                begin, end = _zones_from_response(response)
                if begin == end == zone:
                    _amount_from_response(response)
                    probes.append(ZoneProbe(zone=zone, entry=entry, exit_id=exit_id))
                    found = True
                    break
            if found:
                break
        if not found:
            raise ValueError(f"no single-zone route found for zone {zone}")

    result = tuple(probes)
    _probe_cache[cache_key] = result
    return result
