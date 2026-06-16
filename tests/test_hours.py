from datetime import datetime

from i66tolls.hours import active_direction, toll_window_active


def dt(weekday: int, hour: int, minute: int = 0) -> datetime:
    # 2026-06-08 is a Monday (weekday 0)
    return datetime(2026, 6, 8 + weekday, hour, minute)


def test_eastbound_active_during_morning_window() -> None:
    assert toll_window_active(dt(0, 8, 0), "eastbound")


def test_eastbound_inactive_before_window() -> None:
    assert not toll_window_active(dt(0, 5, 29), "eastbound")


def test_eastbound_inactive_after_window() -> None:
    assert not toll_window_active(dt(0, 9, 31), "eastbound")


def test_westbound_active_during_evening_window() -> None:
    assert toll_window_active(dt(0, 16, 0), "westbound")


def test_westbound_inactive_before_window() -> None:
    assert not toll_window_active(dt(0, 14, 59), "westbound")


def test_no_tolls_on_weekend() -> None:
    assert not toll_window_active(dt(5, 8, 0), "eastbound")
    assert not toll_window_active(dt(6, 16, 0), "westbound")


def test_active_direction_morning() -> None:
    assert active_direction(dt(0, 8, 0)) == "eastbound"


def test_active_direction_evening() -> None:
    assert active_direction(dt(0, 16, 0)) == "westbound"


def test_active_direction_outside_windows() -> None:
    assert active_direction(dt(0, 12, 0)) is None
