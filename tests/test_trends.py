from pathlib import Path

import pytest

from i66tolls.api import Interchange, get_route_zones, get_toll
from i66tolls.trends import PriceTrends, parse_price_trends

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_price_trends_from_fixture() -> None:
    trends = parse_price_trends(read_fixture("chart_data.html"))
    assert trends.week_count == 4
    assert len(trends.eastbound_times) == 16
    assert len(trends.westbound_times) == 16
    times, prices = trends.series("eastbound", 0, 0, 1)
    assert times[0] == "05:30 AM"
    assert len(prices) == 16
    assert prices[8] == 2.45


def test_series_missing_zone_raises() -> None:
    trends = parse_price_trends(read_fixture("chart_data.html"))
    with pytest.raises(ValueError, match="no trend data for zones"):
        trends.series("eastbound", 0, 9, 9)


def test_get_route_zones(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = Interchange(id=1, name="I-66 West", direction="eastbound")
    monkeypatch.setattr(
        "i66tolls.api._fetch",
        lambda handler, params: read_fixture("toll_calc.json"),
    )
    assert get_route_zones(entry, 10) == (0, 1)
