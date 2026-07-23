from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from i66tolls.api import (
    Interchange,
    _parse_entries,
    _parse_options,
    get_toll,
    get_zone_prices,
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


def test_parse_entries_includes_zones() -> None:
    entries = _parse_entries(read_fixture("begin_east.html"), "eastbound")
    assert entries == [
        Interchange(id=1, name="I-66 West", direction="eastbound", zone=0),
        Interchange(id=2, name="I-495 N", direction="eastbound", zone=0),
        Interchange(id=9, name="Glebe Road", direction="eastbound", zone=3),
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
    assert entry.zone == 0


def test_get_zone_prices() -> None:
    def fake_fetch(handler: str, params: dict[str, str]) -> str:
        if handler == "BeginIntPartial":
            return read_fixture("begin_east.html")
        if handler == "ExitIntPartial":
            entry_id = params["bIntId"]
            if entry_id == "1":
                return (
                    '<option value="4">Route 7</option>'
                    '<option value="10">Westmoreland St</option>'
                )
            if entry_id == "9":
                return '<option value="13">Spout Run</option>'
            return '<option value="99">Other</option>'
        if handler == "TollCalcPartial":
            entry_id = params["bIntId"]
            exit_id = params["eIntId"]
            if entry_id == "1" and exit_id == "4":
                return (
                    '{"jsToRun":"runChartMake(1,0,0,\\"I-66 West\\",\\"Route 7\\")",'
                    '"decToll":1.05}'
                )
            if entry_id == "1" and exit_id == "10":
                return (
                    '{"jsToRun":"runChartMake(1,0,1,\\"I-66 West\\",\\"Westmoreland\\")",'
                    '"decToll":3.05}'
                )
            if entry_id == "9" and exit_id == "13":
                return (
                    '{"jsToRun":"runChartMake(1,3,3,\\"Glebe Road\\",\\"Spout Run\\")",'
                    '"decToll":10.0}'
                )
            raise AssertionError(f"unexpected toll calc {params}")
        raise AssertionError(f"unexpected fetch: {handler} {params}")

    at = datetime(2026, 6, 10, 8, 0, tzinfo=EASTERN)
    with patch("i66tolls.api._fetch", side_effect=fake_fetch):
        assert get_zone_prices("eastbound", at=at, is_current=True) == (1.05, 10.0)
