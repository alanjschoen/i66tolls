from pathlib import Path
from unittest.mock import patch

from i66tolls.api import Interchange
from i66tolls.zones import ZoneProbe, clear_probe_cache, resolve_zone_probes

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


def test_resolve_zone_probes_eastbound() -> None:
    clear_probe_cache()
    with patch("i66tolls.api._fetch", side_effect=_fake_fetch):
        probes = resolve_zone_probes("eastbound")
    assert probes == (
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
