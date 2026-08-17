from datetime import date

from i66tolls.storage import (
    DirectionRecord,
    SampleRecord,
    default_data_dir,
    is_day_complete,
    is_direction_complete,
    missing_dates,
    save_direction,
    direction_path,
)


def test_default_data_dir_ends_with_history(monkeypatch) -> None:
    monkeypatch.delenv("I66TOLLS_DATA_DIR", raising=False)
    assert default_data_dir().name == "history"


def test_is_direction_complete_requires_all_samples(tmp_path) -> None:
    day = date(2026, 6, 10)
    record = DirectionRecord(
        schema_version=1,
        date=day.isoformat(),
        direction="eastbound",
        scraped_at="2026-06-10T12:00:00-04:00",
        samples=[
            SampleRecord(time="05:30 AM", zones=[1.0, 2.0, 3.0, 4.0])
        ],
    )
    save_direction(tmp_path, record)
    path = direction_path(tmp_path, day, "eastbound")
    assert not is_direction_complete(path, "eastbound")


def test_is_day_complete_requires_both_directions(tmp_path) -> None:
    day = date(2026, 6, 10)
    samples = [
        SampleRecord(time=time_label, zones=[1.0, 2.0, 3.0, 4.0])
        for time_label in (
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
    ]
    save_direction(
        tmp_path,
        DirectionRecord(
            schema_version=1,
            date=day.isoformat(),
            direction="eastbound",
            scraped_at="2026-06-10T12:00:00-04:00",
            samples=samples,
        ),
    )
    assert not is_day_complete(tmp_path, day)

    west_samples = [
        SampleRecord(time=time_label, zones=[1.0, 2.0, 3.0, 4.0])
        for time_label in (
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
    ]
    save_direction(
        tmp_path,
        DirectionRecord(
            schema_version=1,
            date=day.isoformat(),
            direction="westbound",
            scraped_at="2026-06-10T12:00:00-04:00",
            samples=west_samples,
        ),
    )
    assert is_day_complete(tmp_path, day)


def test_missing_dates_skips_complete_days(tmp_path) -> None:
    day = date(2026, 6, 10)
    samples = [
        SampleRecord(time=time_label, zones=[1.0, 2.0, 3.0, 4.0])
        for time_label in (
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
    ]
    save_direction(
        tmp_path,
        DirectionRecord(
            schema_version=1,
            date=day.isoformat(),
            direction="eastbound",
            scraped_at="2026-06-10T12:00:00-04:00",
            samples=samples,
        ),
    )
    missing = missing_dates(tmp_path, date(2026, 6, 10), date(2026, 6, 10))
    assert missing == [day]
