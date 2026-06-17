"""I-66 inside-the-Beltway tolling hours."""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal, Optional

Direction = Literal["eastbound", "westbound"]

CURRENT_LABEL = "Current estimate"
EASTBOUND_LABEL = "Eastbound (AM, 5:30–9:30)"
WESTBOUND_LABEL = "Westbound (PM, 3:00–7:00)"


def toll_window_active(at: datetime, direction: Direction) -> bool:
    if at.weekday() >= 5:
        return False
    clock = at.time()
    if direction == "eastbound":
        return time(5, 30) <= clock <= time(9, 30)
    return time(15, 0) <= clock <= time(19, 0)


def active_direction(at: datetime) -> Optional[Direction]:
    if toll_window_active(at, "eastbound"):
        return "eastbound"
    if toll_window_active(at, "westbound"):
        return "westbound"
    return None
