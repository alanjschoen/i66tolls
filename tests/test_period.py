from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from i66tolls.period import (
    parse_period,
    scrape_date_range,
    today_eastern,
    weekdays_in_range,
)

EASTERN = ZoneInfo("US/Eastern")
THURSDAY = datetime(2026, 6, 11, 12, 0, tzinfo=EASTERN)


def test_parse_period_days() -> None:
    assert parse_period("7d") == timedelta(days=7)
    assert parse_period("1 day") == timedelta(days=1)


def test_parse_period_weeks() -> None:
    assert parse_period("1 week") == timedelta(weeks=1)
    assert parse_period("2 weeks") == timedelta(weeks=2)


def test_parse_period_months() -> None:
    assert parse_period("1 month") == timedelta(days=30)


def test_parse_period_invalid() -> None:
    with pytest.raises(ValueError, match="invalid period"):
        parse_period("fortnight")


def test_scrape_date_range_ends_yesterday() -> None:
    start, end = scrape_date_range("1 week", now=THURSDAY)
    assert end == date(2026, 6, 10)
    assert start == date(2026, 6, 4)


def test_scrape_date_range_skips_today() -> None:
    today = today_eastern(now=THURSDAY)
    _, end = scrape_date_range("1 day", now=THURSDAY)
    assert end < today


def test_weekdays_in_range_skips_weekends() -> None:
    days = weekdays_in_range(date(2026, 6, 5), date(2026, 6, 8))
    assert days == [date(2026, 6, 5), date(2026, 6, 8)]
