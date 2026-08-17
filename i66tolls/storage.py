"""Local storage for scraped toll history."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from i66tolls.period import is_weekday, weekdays_in_range
from i66tolls.trends import EASTBOUND_SAMPLE_TIMES, WESTBOUND_SAMPLE_TIMES

EASTERN = ZoneInfo("US/Eastern")
SCHEMA_VERSION = 1

Direction = Literal["eastbound", "westbound"]
DIRECTIONS: tuple[Direction, ...] = ("eastbound", "westbound")

EXPECTED_SAMPLES: dict[Direction, int] = {
    "eastbound": len(EASTBOUND_SAMPLE_TIMES),
    "westbound": len(WESTBOUND_SAMPLE_TIMES),
}


def default_data_dir() -> Path:
    override = os.environ.get("I66TOLLS_DATA_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "i66tolls" / "history"


def day_dir(data_dir: Path, day: date) -> Path:
    return data_dir / day.isoformat()


def direction_path(data_dir: Path, day: date, direction: Direction) -> Path:
    return day_dir(data_dir, day) / f"{direction}.json"


@dataclass
class SampleRecord:
    time: str
    zones: list[Optional[float]]
    errors: list[str] = field(default_factory=list)


@dataclass
class DirectionRecord:
    schema_version: int
    date: str
    direction: Direction
    scraped_at: str
    samples: list[SampleRecord]

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "date": self.date,
            "direction": self.direction,
            "scraped_at": self.scraped_at,
            "samples": [
                {
                    "time": sample.time,
                    "zones": sample.zones,
                    **({"errors": sample.errors} if sample.errors else {}),
                }
                for sample in self.samples
            ],
        }
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> DirectionRecord:
        raw_samples = payload.get("samples", [])
        samples: list[SampleRecord] = []
        if isinstance(raw_samples, list):
            for item in raw_samples:
                if not isinstance(item, dict):
                    continue
                errors_raw = item.get("errors", [])
                errors = (
                    [str(error) for error in errors_raw]
                    if isinstance(errors_raw, list)
                    else []
                )
                zones_raw = item.get("zones", [])
                zones = (
                    [None if value is None else float(value) for value in zones_raw]
                    if isinstance(zones_raw, list)
                    else []
                )
                samples.append(
                    SampleRecord(
                        time=str(item.get("time", "")),
                        zones=zones,
                        errors=errors,
                    )
                )
        return cls(
            schema_version=int(payload.get("schema_version", 0)),
            date=str(payload.get("date", "")),
            direction=str(payload.get("direction", "")),  # type: ignore[arg-type]
            scraped_at=str(payload.get("scraped_at", "")),
            samples=samples,
        )


def load_direction(path: Path) -> Optional[DirectionRecord]:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return None
    return DirectionRecord.from_dict(payload)


def save_direction(data_dir: Path, record: DirectionRecord) -> Path:
    path = direction_path(data_dir, date.fromisoformat(record.date), record.direction)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), indent=2) + "\n")
    return path


def is_direction_complete(path: Path, direction: Direction) -> bool:
    record = load_direction(path)
    if record is None:
        return False
    return len(record.samples) >= EXPECTED_SAMPLES[direction]


def is_day_complete(data_dir: Path, day: date) -> bool:
    if not is_weekday(day):
        return True
    return all(
        is_direction_complete(direction_path(data_dir, day, direction), direction)
        for direction in DIRECTIONS
    )


def list_stored_dates(data_dir: Path) -> list[date]:
    if not data_dir.is_dir():
        return []
    dates: list[date] = []
    for entry in data_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            dates.append(date.fromisoformat(entry.name))
        except ValueError:
            continue
    return sorted(dates)


def missing_dates(data_dir: Path, start: date, end: date) -> list[date]:
    return [
        day
        for day in weekdays_in_range(start, end)
        if not is_day_complete(data_dir, day)
    ]


def new_scraped_at(*, now: Optional[datetime] = None) -> str:
    when = now.astimezone(EASTERN) if now is not None else datetime.now(EASTERN)
    return when.isoformat()
