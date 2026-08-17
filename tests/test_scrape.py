from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from i66tolls.api import Interchange
from i66tolls.scrape import _count_scrape_steps, format_summary, run_scrape, scrape_direction
from i66tolls.storage import direction_path, is_day_complete, load_direction
from i66tolls.zones import ZoneProbe

EASTERN = ZoneInfo("US/Eastern")
THURSDAY = datetime(2026, 6, 11, 12, 0, tzinfo=EASTERN)
FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def _fake_fetch(handler: str, params: dict[str, str]) -> str:
    if handler == "BeginIntPartial":
        if params["rbEastVal"] == "true":
            return read_fixture("begin_east.html")
        return read_fixture("begin_west.html")
    if handler == "ExitIntPartial":
        entry_id = params["bIntId"]
        if entry_id == "1":
            return read_fixture("exit_from_1_east.html")
        if entry_id == "9":
            return '<option value="13">Spout Run</option>'
        if entry_id == "16":
            return '<option value="15">Rosslyn</option>'
        if entry_id == "12":
            return '<option value="11">Other</option>'
        return '<option value="99">Other</option>'
    if handler == "TollCalcPartial":
        if params.get("timePicked") == "05:45 AM" and params.get("bIntId") == "1":
            return '{"jsToRun":"runChartMake(1,0,0,\\"I-66 West\\",\\"Route 7\\")","decToll":-1}'
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
        if entry_id == "16" and exit_id == "15":
            return (
                '{"jsToRun":"runChartMake(1,4,4,\\"Washington\\",\\"Rosslyn\\")",'
                '"decToll":2.0}'
            )
        if entry_id == "12" and exit_id == "11":
            return (
                '{"jsToRun":"runChartMake(1,5,5,\\"Fairfax Drive\\",\\"Other\\")",'
                '"decToll":4.0}'
            )
        raise AssertionError(f"unexpected toll calc {params}")
    raise AssertionError(f"unexpected fetch: {handler} {params}")


def test_count_scrape_steps(tmp_path) -> None:
    day = date(2026, 6, 10)
    probes = {
        "eastbound": (
            ZoneProbe(
                zone=0,
                entry=Interchange(id=1, name="I-66 West", direction="eastbound", zone=0),
                exit_id=4,
            ),
        ),
        "westbound": (
            ZoneProbe(
                zone=4,
                entry=Interchange(id=16, name="Washington", direction="westbound", zone=4),
                exit_id=15,
            ),
        ),
    }
    assert _count_scrape_steps(tmp_path, [day], probes) == 32


def test_dry_run_lists_missing_dates(tmp_path) -> None:
    summary = run_scrape("1 week", data_dir=tmp_path, dry_run=True, now=THURSDAY)
    assert summary.planned
    assert summary.fetched == []
    assert "dates to fetch" in format_summary(summary)


def test_scrape_direction_continues_on_sample_failure(tmp_path) -> None:
    day = date(2026, 6, 10)
    probes = (
        ZoneProbe(
            zone=0,
            entry=Interchange(id=1, name="I-66 West", direction="eastbound", zone=0),
            exit_id=4,
        ),
        ZoneProbe(
            zone=3,
            entry=Interchange(id=9, name="Glebe Road", direction="eastbound", zone=3),
            exit_id=13,
        ),
    )
    with patch("i66tolls.api._fetch", side_effect=_fake_fetch):
        record = scrape_direction(tmp_path, day, "eastbound", probes)
    assert len(record.samples) == 16
    unavailable = next(sample for sample in record.samples if sample.time == "05:45 AM")
    assert unavailable.zones[0] is None
    assert unavailable.zones[1] == 10.0


@patch("i66tolls.scrape.RateLimitedClient")
def test_run_scrape_saves_complete_day(client_cls: object, tmp_path) -> None:
    client_cls.return_value.fetch.side_effect = _fake_fetch
    summary = run_scrape(
        "1 day",
        data_dir=tmp_path,
        delay=0,
        jitter=0,
        show_progress=False,
        now=THURSDAY,
    )
    assert summary.fetched == [date(2026, 6, 10)]
    assert is_day_complete(tmp_path, date(2026, 6, 10))
    east = load_direction(direction_path(tmp_path, date(2026, 6, 10), "eastbound"))
    assert east is not None
    assert len(east.samples) == 16
