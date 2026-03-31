"""Trade-scaling and execution logic.

Given a :class:`~copycat.signal_sources.base.TradeSignal` (the leader's
position) and our current USDT balance, this module:

1. Calculates a scaled quantity so we never risk more than
   ``config.max_position_size * balance`` per position.
2. Validates the symbol against Binance's active trading pairs.
3. Sets leverage and places a market order.
"""

from __future__ import annotations

import logging
import math

from .binance_client import BinanceClient
from .config import Config
from .portfolio import MirroredPosition, Portfolio
from .signal_sources.base import TradeSignal

logger = logging.getLogger(__name__)


def _round_down(value: float, precision: int) -> float:
    """Round *value* DOWN to *precision* decimal places (avoids over-buying)."""
    factor = 10 ** precision
    return math.floor(value * factor) / factor


class Trader:
    """Executes scaled copy-trades on Binance Futures."""

    def __init__(
        self,
        client: BinanceClient,
        portfolio: Portfolio,
        config: Config,
    ) -> None:
        self._client = client
        self._portfolio = portfolio
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_position(self, signal: TradeSignal, balance: float) -> bool:
        """Open a new mirrored position for *signal*.

        Returns True on success, False if the position was skipped.
        """
        symbol = signal.symbol.upper()

        # --- Guard: only act on Binance-supported symbols ---------------
        if not self._client.is_valid_symbol(symbol):
            logger.warning("Symbol %s is not traded on Binance Futures – skipping.", symbol)
            return False

        # --- Guard: position already open --------------------------------
        if self._portfolio.is_open(symbol, signal.source_trader_id):
            logger.debug("Position %s / %s already mirrored.", symbol, signal.source_trader_id)
            return False

        # --- Guard: portfolio cap ----------------------------------------
        if not self._portfolio.can_open_new():
            logger.info("Portfolio is full (%d positions). Skipping %s.", self._portfolio.open_count(), symbol)
            return False

        # --- Scale the order size ----------------------------------------
        quantity = self._calculate_quantity(signal, balance)
        if quantity is None:
            return False

        # --- Set leverage -------------------------------------------------
        try:
            self._client.set_leverage(symbol, self._config.futures_leverage)
        except Exception:
            logger.warning("Failed to set leverage for %s; proceeding anyway.", symbol)

        # --- Place market order ------------------------------------------
        order_side = "BUY" if signal.side == "LONG" else "SELL"
        try:
            order = self._client.place_market_order(symbol, order_side, quantity)
        except Exception as exc:
            logger.error("Could not open position for %s: %s", symbol, exc)
            return False

        # --- Record in portfolio -----------------------------------------
        fill_price = float(order.get("avgPrice") or signal.mark_price)
        self._portfolio.add(
            MirroredPosition(
                symbol=symbol,
                side=signal.side,
                quantity=quantity,
                entry_price=fill_price,
                leader_trader_id=signal.source_trader_id,
                order_id=str(order.get("orderId", "")),
            )
        )
        return True

    def close_position(self, symbol: str, leader_trader_id: str) -> bool:
        """Close a mirrored position that the leader has exited.

        Returns True on success, False if nothing was closed.
        """
        symbol = symbol.upper()
        pos = self._portfolio.positions.get((symbol, leader_trader_id))
        if pos is None:
            logger.debug("No mirrored position for %s / %s.", symbol, leader_trader_id)
            return False

        position_amt = pos.quantity if pos.side == "LONG" else -pos.quantity
        try:
            self._client.close_position(symbol, position_amt)
        except Exception as exc:
            logger.error("Could not close position %s: %s", symbol, exc)
            return False

        self._portfolio.remove(symbol, leader_trader_id)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _calculate_quantity(
        self, signal: TradeSignal, balance: float
    ) -> float | None:
        """Return a position size in base currency, scaled to our bankroll.

        Formula
        -------
        We allocate at most ``max_position_size * balance * leverage`` USDT
        in notional value, then divide by the current mark price to get the
        quantity in base currency.
        """
        if signal.mark_price <= 0:
            logger.warning("Mark price for %s is 0 – skipping.", signal.symbol)
            return None

        max_notional = self._config.max_position_size * balance * self._config.futures_leverage
        quantity_raw = max_notional / signal.mark_price

        precision = self._client.get_quantity_precision(signal.symbol)
        quantity = _round_down(quantity_raw, precision)

        if quantity <= 0:
            logger.warning(
                "Calculated quantity for %s is 0 (balance=%.2f, price=%.2f). "
                "Not enough balance.",
                signal.symbol,
                balance,
                signal.mark_price,
            )
            return None

        logger.debug(
            "Scaling %s: balance=%.2f, notional=%.2f, price=%.2f, qty=%.6f",
            signal.symbol,
            balance,
            max_notional,
            signal.mark_price,
            quantity,
        )
        return quantity
