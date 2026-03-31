"""Tests for copycat.trader (trade scaling and execution)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import MagicMock, patch
from copycat.config import Config
from copycat.portfolio import Portfolio, MirroredPosition
from copycat.signal_sources.base import TradeSignal
from copycat.trader import Trader, _round_down


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**kwargs) -> Config:
    defaults = dict(
        api_key="key",
        api_secret="secret",
        max_position_size=0.05,
        max_open_positions=10,
        futures_leverage=5,
    )
    defaults.update(kwargs)
    return Config(**defaults)


def _make_signal(**kwargs) -> TradeSignal:
    defaults = dict(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=30000.0,
        mark_price=30000.0,
        leverage=5,
        amount=1500.0,
        source_trader_id="uid_1",
    )
    defaults.update(kwargs)
    return TradeSignal(**defaults)


def _make_trader(config=None, portfolio=None):
    config = config or _make_config()
    portfolio = portfolio or Portfolio()
    mock_client = MagicMock()
    mock_client.is_valid_symbol.return_value = True
    mock_client.get_quantity_precision.return_value = 3
    mock_client.set_leverage.return_value = {}
    mock_client.place_market_order.return_value = {
        "orderId": "ord_1",
        "avgPrice": "30000.0",
    }
    return Trader(mock_client, portfolio, config), mock_client, portfolio


# ---------------------------------------------------------------------------
# _round_down helper
# ---------------------------------------------------------------------------

class TestRoundDown:
    def test_rounds_down_not_up(self):
        assert _round_down(1.9999, 3) == pytest.approx(1.999)

    def test_zero_precision(self):
        assert _round_down(3.7, 0) == 3.0

    def test_already_exact(self):
        assert _round_down(1.5, 2) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# open_position
# ---------------------------------------------------------------------------

class TestOpenPosition:
    def test_opens_valid_long(self):
        trader, client, portfolio = _make_trader()
        sig = _make_signal(side="LONG", mark_price=30000.0)
        result = trader.open_position(sig, balance=10000.0)
        assert result is True
        client.place_market_order.assert_called_once()
        call_args = client.place_market_order.call_args
        assert call_args[0][1] == "BUY"

    def test_opens_valid_short(self):
        trader, client, portfolio = _make_trader()
        sig = _make_signal(side="SHORT", mark_price=2000.0)
        trader.open_position(sig, balance=10000.0)
        call_args = client.place_market_order.call_args
        assert call_args[0][1] == "SELL"

    def test_skips_invalid_symbol(self):
        trader, client, portfolio = _make_trader()
        client.is_valid_symbol.return_value = False
        sig = _make_signal(symbol="FAKECOIN")
        result = trader.open_position(sig, balance=10000.0)
        assert result is False
        client.place_market_order.assert_not_called()

    def test_skips_already_open_position(self):
        portfolio = Portfolio()
        portfolio.add(
            MirroredPosition("BTCUSDT", "LONG", 0.001, 30000.0, "uid_1", "x")
        )
        trader, client, _ = _make_trader(portfolio=portfolio)
        result = trader.open_position(_make_signal(), balance=10000.0)
        assert result is False
        client.place_market_order.assert_not_called()

    def test_skips_when_portfolio_full(self):
        config = _make_config(max_open_positions=1)
        portfolio = Portfolio(max_open_positions=1)
        portfolio.add(MirroredPosition("ETHUSDT", "LONG", 0.1, 2000.0, "uid_2", "y"))
        trader, client, _ = _make_trader(config=config, portfolio=portfolio)
        result = trader.open_position(_make_signal(), balance=10000.0)
        assert result is False
        client.place_market_order.assert_not_called()

    def test_skips_zero_mark_price(self):
        trader, client, _ = _make_trader()
        sig = _make_signal(mark_price=0.0)
        result = trader.open_position(sig, balance=10000.0)
        assert result is False
        client.place_market_order.assert_not_called()

    def test_quantity_scaling(self):
        """qty = floor(max_pos_size * balance * leverage / price, precision)."""
        config = _make_config(max_position_size=0.10, futures_leverage=2)
        trader, client, _ = _make_trader(config=config)
        # Expected: 0.10 * 5000 * 2 / 40000 = 0.025, precision=3 → 0.025
        sig = _make_signal(mark_price=40000.0)
        trader.open_position(sig, balance=5000.0)
        call_args = client.place_market_order.call_args
        assert call_args[0][2] == pytest.approx(0.025, rel=1e-3)

    def test_returns_false_on_order_failure(self):
        trader, client, _ = _make_trader()
        from binance.exceptions import BinanceAPIException
        client.place_market_order.side_effect = BinanceAPIException(
            MagicMock(status_code=400), 400, '{"code": -1000, "msg": "err"}'
        )
        result = trader.open_position(_make_signal(), balance=10000.0)
        assert result is False

    def test_position_added_to_portfolio(self):
        trader, client, portfolio = _make_trader()
        trader.open_position(_make_signal(), balance=10000.0)
        assert portfolio.is_open("BTCUSDT", "uid_1") is True


# ---------------------------------------------------------------------------
# close_position
# ---------------------------------------------------------------------------

class TestClosePosition:
    def test_closes_open_position(self):
        portfolio = Portfolio()
        portfolio.add(MirroredPosition("BTCUSDT", "LONG", 0.01, 30000.0, "uid_1"))
        trader, client, _ = _make_trader(portfolio=portfolio)
        result = trader.close_position("BTCUSDT", "uid_1")
        assert result is True
        client.close_position.assert_called_once()
        assert not portfolio.is_open("BTCUSDT", "uid_1")

    def test_returns_false_for_unknown_position(self):
        trader, client, _ = _make_trader()
        result = trader.close_position("ETHUSDT", "uid_99")
        assert result is False
        client.close_position.assert_not_called()

    def test_short_position_closed_as_buy(self):
        portfolio = Portfolio()
        portfolio.add(MirroredPosition("ETHUSDT", "SHORT", 1.0, 2000.0, "uid_2"))
        trader, client, _ = _make_trader(portfolio=portfolio)
        trader.close_position("ETHUSDT", "uid_2")
        call_args = client.close_position.call_args
        # position_amt is negative for SHORT
        assert call_args[0][1] == pytest.approx(-1.0)
