"""Tests for BinanceLeaderboardSource (uses mocked HTTP responses)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from copycat.signal_sources.binance_leaderboard import BinanceLeaderboardSource
from copycat.signal_sources.base import TraderSignal


_LEADERBOARD_RESPONSE = {
    "data": [
        {
            "encryptedUid": "uid_1",
            "nickName": "AlphaTrader",
            "roi": 1.50,          # 150 %
            "pnl": 15000.0,
            "followerCount": 300,
            "periodDurationInDay": 45,
        },
        {
            "encryptedUid": "uid_2",
            "nickName": "LowROI",
            "roi": 0.20,          # 20 % – below min_roi=50
            "pnl": 500.0,
            "followerCount": 10,
            "periodDurationInDay": 60,
        },
        {
            "encryptedUid": "uid_3",
            "nickName": "NewTrader",
            "roi": 2.00,          # 200 % but too new
            "pnl": 20000.0,
            "followerCount": 50,
            "periodDurationInDay": 5,  # below min_days=30
        },
    ]
}

_POSITION_RESPONSE = {
    "data": {
        "otherPositionRetList": [
            {
                "symbol": "BTCUSDT",
                "amount": 0.05,      # positive = LONG
                "entryPrice": 29000.0,
                "markPrice": 30000.0,
                "leverage": 10,
            },
            {
                "symbol": "ETHUSDT",
                "amount": -1.5,     # negative = SHORT
                "entryPrice": 1800.0,
                "markPrice": 1750.0,
                "leverage": 5,
            },
            {
                # missing symbol – should be skipped
                "symbol": "",
                "amount": 1.0,
                "entryPrice": 100.0,
                "markPrice": 100.0,
                "leverage": 1,
            },
        ]
    }
}


@pytest.fixture()
def source():
    return BinanceLeaderboardSource()


@pytest.fixture()
def trader() -> TraderSignal:
    return TraderSignal(
        trader_id="uid_1",
        nickname="AlphaTrader",
        roi=150.0,
        pnl=15000.0,
        followers=300,
        days_active=45,
    )


class TestFetchTopTraders:
    def test_filters_by_roi(self, source, mocker):
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value=_LEADERBOARD_RESPONSE,
        )
        traders = source.fetch_top_traders(top_n=10, min_roi=50.0, min_days=30, period="MONTHLY")
        names = [t.nickname for t in traders]
        assert "AlphaTrader" in names
        assert "LowROI" not in names

    def test_filters_by_min_days(self, source, mocker):
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value=_LEADERBOARD_RESPONSE,
        )
        traders = source.fetch_top_traders(top_n=10, min_roi=50.0, min_days=30, period="MONTHLY")
        names = [t.nickname for t in traders]
        assert "NewTrader" not in names

    def test_respects_top_n(self, source, mocker):
        # Response has more rows than top_n=1
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value={
                "data": [
                    {"encryptedUid": f"uid_{i}", "nickName": f"T{i}",
                     "roi": 2.0, "pnl": 1000.0, "followerCount": 100,
                     "periodDurationInDay": 60}
                    for i in range(5)
                ]
            },
        )
        traders = source.fetch_top_traders(top_n=2, min_roi=0.0, min_days=0, period="MONTHLY")
        assert len(traders) == 2

    def test_returns_empty_on_request_error(self, source, mocker):
        import requests
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            side_effect=requests.RequestException("network error"),
        )
        traders = source.fetch_top_traders(top_n=5, min_roi=0.0, min_days=0, period="MONTHLY")
        assert traders == []

    def test_roi_conversion(self, source, mocker):
        """API returns fraction; we convert to percentage."""
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value={
                "data": [
                    {"encryptedUid": "u1", "nickName": "T1", "roi": 0.75,
                     "pnl": 0, "followerCount": 0, "periodDurationInDay": 60}
                ]
            },
        )
        traders = source.fetch_top_traders(top_n=5, min_roi=50.0, min_days=0, period="MONTHLY")
        assert len(traders) == 1
        assert traders[0].roi == pytest.approx(75.0)


class TestFetchPositions:
    def test_parses_long_position(self, source, trader, mocker):
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value=_POSITION_RESPONSE,
        )
        positions = source.fetch_positions(trader)
        btc = next(p for p in positions if p.symbol == "BTCUSDT")
        assert btc.side == "LONG"
        assert btc.entry_price == pytest.approx(29000.0)
        assert btc.mark_price == pytest.approx(30000.0)
        assert btc.leverage == 10

    def test_parses_short_position(self, source, trader, mocker):
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value=_POSITION_RESPONSE,
        )
        positions = source.fetch_positions(trader)
        eth = next(p for p in positions if p.symbol == "ETHUSDT")
        assert eth.side == "SHORT"

    def test_skips_missing_symbol(self, source, trader, mocker):
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            return_value=_POSITION_RESPONSE,
        )
        positions = source.fetch_positions(trader)
        assert all(p.symbol for p in positions)
        assert len(positions) == 2  # empty-symbol entry dropped

    def test_returns_empty_on_request_error(self, source, trader, mocker):
        import requests
        mocker.patch(
            "copycat.signal_sources.binance_leaderboard._post",
            side_effect=requests.RequestException("timeout"),
        )
        positions = source.fetch_positions(trader)
        assert positions == []

    def test_source_name(self, source):
        assert source.name == "Binance Leaderboard"
