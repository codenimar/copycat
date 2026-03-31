"""Tests for copycat.portfolio."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from copycat.portfolio import MirroredPosition, Portfolio


def _pos(symbol="BTCUSDT", side="LONG", qty=0.001, leader="uid_1"):
    return MirroredPosition(
        symbol=symbol,
        side=side,
        quantity=qty,
        entry_price=30000.0,
        leader_trader_id=leader,
        order_id="order_123",
    )


class TestPortfolio:
    def test_empty_on_init(self):
        p = Portfolio(max_open_positions=10)
        assert p.open_count() == 0
        assert p.all_positions() == []

    def test_can_open_new_when_below_cap(self):
        p = Portfolio(max_open_positions=3)
        assert p.can_open_new() is True

    def test_can_open_new_false_when_at_cap(self):
        p = Portfolio(max_open_positions=1)
        p.add(_pos())
        assert p.can_open_new() is False

    def test_is_open_after_add(self):
        p = Portfolio()
        pos = _pos()
        p.add(pos)
        assert p.is_open("BTCUSDT", "uid_1") is True

    def test_is_open_case_insensitive_symbol(self):
        p = Portfolio()
        p.add(_pos(symbol="BTCUSDT"))
        assert p.is_open("btcusdt", "uid_1") is True

    def test_is_open_false_for_different_leader(self):
        p = Portfolio()
        p.add(_pos(leader="uid_1"))
        assert p.is_open("BTCUSDT", "uid_2") is False

    def test_remove_returns_position(self):
        p = Portfolio()
        p.add(_pos())
        removed = p.remove("BTCUSDT", "uid_1")
        assert removed is not None
        assert removed.symbol == "BTCUSDT"
        assert p.open_count() == 0

    def test_remove_returns_none_for_unknown(self):
        p = Portfolio()
        assert p.remove("ETHUSDT", "uid_99") is None

    def test_multiple_positions_different_leaders(self):
        p = Portfolio(max_open_positions=5)
        p.add(_pos(symbol="BTCUSDT", leader="leader_1"))
        p.add(_pos(symbol="BTCUSDT", leader="leader_2"))
        p.add(_pos(symbol="ETHUSDT", leader="leader_1"))
        assert p.open_count() == 3

    def test_all_positions(self):
        p = Portfolio()
        p.add(_pos(symbol="BTCUSDT"))
        p.add(_pos(symbol="ETHUSDT", leader="uid_2"))
        syms = {pos.symbol for pos in p.all_positions()}
        assert syms == {"BTCUSDT", "ETHUSDT"}
