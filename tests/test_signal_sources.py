"""Tests for copycat.signal_sources.base (TradeSignal / TraderSignal)."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from copycat.signal_sources.base import TradeSignal, TraderSignal


def _make_signal(**kwargs) -> TradeSignal:
    defaults = dict(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=30000.0,
        mark_price=30100.0,
        leverage=5,
        amount=1000.0,
        source_trader_id="trader_abc",
    )
    defaults.update(kwargs)
    return TradeSignal(**defaults)


class TestTradeSignal:
    def test_symbol_is_uppercased(self):
        sig = _make_signal(symbol="btcusdt")
        assert sig.symbol == "BTCUSDT"

    def test_side_is_uppercased(self):
        sig = _make_signal(side="long")
        assert sig.side == "LONG"

    def test_short_side_accepted(self):
        sig = _make_signal(side="short")
        assert sig.side == "SHORT"

    def test_invalid_side_raises(self):
        with pytest.raises(ValueError, match="side must be"):
            _make_signal(side="NEUTRAL")

    def test_extra_defaults_to_empty_dict(self):
        sig = _make_signal()
        assert sig.extra == {}

    def test_extra_stores_custom_data(self):
        sig = _make_signal(extra={"foo": "bar"})
        assert sig.extra["foo"] == "bar"


class TestTraderSignal:
    def test_positions_default_empty(self):
        trader = TraderSignal(
            trader_id="t1",
            nickname="Alice",
            roi=150.0,
            pnl=5000.0,
            followers=200,
            days_active=60,
        )
        assert trader.positions == []

    def test_positions_stored(self):
        sig = _make_signal()
        trader = TraderSignal(
            trader_id="t1",
            nickname="Bob",
            roi=200.0,
            pnl=10000.0,
            followers=500,
            days_active=90,
            positions=[sig],
        )
        assert len(trader.positions) == 1
        assert trader.positions[0].symbol == "BTCUSDT"
