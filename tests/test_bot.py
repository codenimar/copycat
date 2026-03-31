"""Tests for CopycatBot orchestration."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from copycat.bot import CopycatBot
from copycat.config import Config
from copycat.signal_sources.base import TraderSignal, TradeSignal


def _make_config(**kwargs):
    defaults = dict(
        api_key="k",
        api_secret="s",
        max_position_size=0.05,
        max_open_positions=10,
        futures_leverage=5,
        sync_interval=1,
        leaderboard_top_n=2,
        leaderboard_min_roi=50.0,
        leaderboard_min_days=30,
        leaderboard_period="MONTHLY",
    )
    defaults.update(kwargs)
    return Config(**defaults)


def _make_trader_signal(trader_id="uid_1", nickname="Alice", roi=100.0):
    return TraderSignal(
        trader_id=trader_id,
        nickname=nickname,
        roi=roi,
        pnl=5000.0,
        followers=100,
        days_active=60,
    )


def _make_trade_signal(symbol="BTCUSDT", side="LONG", trader_id="uid_1"):
    return TradeSignal(
        symbol=symbol,
        side=side,
        entry_price=30000.0,
        mark_price=30000.0,
        leverage=5,
        amount=1500.0,
        source_trader_id=trader_id,
    )


@pytest.fixture()
def mock_source():
    source = MagicMock()
    source.name = "MockSource"
    source.fetch_top_traders.return_value = [_make_trader_signal()]
    source.fetch_positions.return_value = [_make_trade_signal()]
    return source


@pytest.fixture()
def bot(mock_source):
    cfg = _make_config()
    with (
        patch("copycat.bot.BinanceClient") as MockClient,
    ):
        mock_client = MockClient.return_value
        mock_client.get_futures_balance.return_value = 10000.0
        mock_client.is_valid_symbol.return_value = True
        mock_client.get_quantity_precision.return_value = 3
        mock_client.get_valid_symbols.return_value = {"BTCUSDT", "ETHUSDT"}
        mock_client.set_leverage.return_value = {}
        mock_client.place_market_order.return_value = {
            "orderId": "o1", "avgPrice": "30000"
        }
        mock_client.get_open_positions.return_value = []

        b = CopycatBot(config=cfg, signal_source=mock_source)
        b._client = mock_client
        yield b


class TestRunOnce:
    def test_opens_new_position(self, bot, mock_source):
        summary = bot.run_once()
        assert summary["opened"] == 1
        assert summary["closed"] == 0

    def test_no_traders_returns_zeroes(self, bot, mock_source):
        mock_source.fetch_top_traders.return_value = []
        summary = bot.run_once()
        assert summary == {"opened": 0, "closed": 0, "skipped": 0, "errors": 0}

    def test_closes_stale_position(self, bot, mock_source):
        # Pre-populate portfolio with a position the leader has exited
        from copycat.portfolio import MirroredPosition
        bot._portfolio.add(
            MirroredPosition("SOLUSDT", "LONG", 0.5, 100.0, "uid_1")
        )
        # leader no longer holds SOLUSDT
        mock_source.fetch_positions.return_value = [_make_trade_signal("BTCUSDT")]
        bot._client.close_position.return_value = {"orderId": "close_1"}

        summary = bot.run_once()
        assert summary["closed"] == 1

    def test_skips_invalid_symbol(self, bot, mock_source):
        bot._client.is_valid_symbol.return_value = False
        summary = bot.run_once()
        assert summary["opened"] == 0
        assert summary["skipped"] == 1

    def test_balance_failure_aborts_cycle(self, bot):
        bot._client.get_futures_balance.side_effect = Exception("API error")
        summary = bot.run_once()
        assert summary["opened"] == 0

    def test_does_not_duplicate_open_position(self, bot, mock_source):
        # First cycle opens the position
        bot.run_once()
        # Second cycle should not open again
        summary = bot.run_once()
        assert summary["opened"] == 0


class TestBotInit:
    def test_invalid_config_raises(self):
        bad_cfg = _make_config(max_position_size=2.0)
        with pytest.raises(ValueError):
            CopycatBot(config=bad_cfg)

    def test_default_source_is_binance_leaderboard(self):
        cfg = _make_config()
        with patch("copycat.bot.BinanceClient"):
            bot = CopycatBot(config=cfg)
        from copycat.signal_sources.binance_leaderboard import BinanceLeaderboardSource
        assert isinstance(bot._source, BinanceLeaderboardSource)
