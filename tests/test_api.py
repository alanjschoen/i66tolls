from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from i66tolls.api import (
    Interchange,
    _parse_options,
    get_toll,
    infer_direction,
    lookup_entry,
)

FIXTURES = Path(__file__).parent / "fixtures"
EASTERN = ZoneInfo("US/Eastern")


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_options_skips_empty_values() -> None:
    html = read_fixture("begin_east.html")
    assert _parse_options(html) == [
        (1, "I-66 West"),
        (2, "I-495 N"),
        (9, "Glebe Road"),
    ]


def test_get_toll_returns_amount() -> None:
    entry = Interchange(id=1, name="I-66 West", direction="eastbound")
    at = datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN)
    with patch("i66tolls.api._fetch", return_value=read_fixture("toll_calc.json")):
        assert get_toll(entry, 10, at=at, is_current=False) == 4.5


def test_get_toll_returns_none_for_unavailable() -> None:
    entry = Interchange(id=1, name="I-66 West", direction="eastbound")
    at = datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN)
    with patch("i66tolls.api._fetch", return_value=read_fixture("toll_unavailable.json")):
        assert get_toll(entry, 10, at=at, is_current=False) is None


def test_get_toll_request_params() -> None:
    entry = Interchange(id=1, name="I-66 West", direction="eastbound")
    at = datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN)
    with patch("i66tolls.api._fetch", return_value=read_fixture("toll_calc.json")) as fetch:
        get_toll(entry, 10, at=at, is_current=True)
    handler, params = fetch.call_args.args
    assert handler == "TollCalcPartial"
    assert params["bIntId"] == "1"
    assert params["eIntId"] == "10"
    assert params["datePicked"] == "06/10/2026"
    assert params["timePicked"] == "08:00 AM"
    assert params["rbEastVal"] == "true"
    assert params["isCurrent"] == "true"


def _fake_fetch(handler: str, params: dict[str, str]) -> str:
    if handler == "BeginIntPartial":
        if params["rbEastVal"] == "true":
            return read_fixture("begin_east.html")
        return read_fixture("begin_west.html")
    if handler == "ExitIntPartial":
        return read_fixture("exit_from_1_east.html")
    raise AssertionError(f"unexpected fetch: {handler} {params}")


def test_infer_direction_eastbound() -> None:
    with patch("i66tolls.api._fetch", side_effect=_fake_fetch):
        assert infer_direction(1, 10) == "eastbound"


def test_infer_direction_unknown_route() -> None:
    with patch("i66tolls.api._fetch", side_effect=_fake_fetch):
        with pytest.raises(ValueError, match="No route found"):
            infer_direction(1, 99)


def test_lookup_entry() -> None:
    with patch("i66tolls.api._fetch", side_effect=_fake_fetch):
        entry = lookup_entry(1, "eastbound")
    assert entry.id == 1
    assert entry.name == "I-66 West"
    assert entry.direction == "eastbound"
