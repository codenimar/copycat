"""Thin wrapper around the Binance Futures API.

Responsibilities
----------------
* Maintain the authorised client (live or testnet).
* Cache the set of valid Binance Futures symbols so pair validation is O(1).
* Provide simple helpers for balance, open positions, order placement,
  and leverage management.
"""

from __future__ import annotations

import logging
from typing import Optional

from binance.client import Client
from binance.exceptions import BinanceAPIException

from .config import Config

logger = logging.getLogger(__name__)


class BinanceClient:
    """Manages interaction with Binance Futures (USDT-M)."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._client = Client(
            api_key=config.api_key,
            api_secret=config.api_secret,
            testnet=config.testnet,
        )
        self._valid_symbols: Optional[set[str]] = None

    # ------------------------------------------------------------------
    # Symbol validation
    # ------------------------------------------------------------------

    def get_valid_symbols(self) -> set[str]:
        """Return the set of active Binance Futures (USDT-M) symbols."""
        if self._valid_symbols is None:
            info = self._client.futures_exchange_info()
            self._valid_symbols = {
                s["symbol"]
                for s in info["symbols"]
                if s["status"] == "TRADING"
            }
        return self._valid_symbols

    def is_valid_symbol(self, symbol: str) -> bool:
        """Return True if *symbol* is actively traded on Binance Futures."""
        return symbol.upper() in self.get_valid_symbols()

    # ------------------------------------------------------------------
    # Account / balance helpers
    # ------------------------------------------------------------------

    def get_futures_balance(self) -> float:
        """Return available USDT balance in the Futures wallet."""
        try:
            balances = self._client.futures_account_balance()
            for b in balances:
                if b["asset"] == "USDT":
                    return float(b["availableBalance"])
            return 0.0
        except BinanceAPIException as exc:
            logger.error("Failed to fetch futures balance: %s", exc)
            raise

    def get_open_positions(self) -> list[dict]:
        """Return all currently open Futures positions (non-zero quantity)."""
        try:
            positions = self._client.futures_position_information()
            return [p for p in positions if float(p["positionAmt"]) != 0.0]
        except BinanceAPIException as exc:
            logger.error("Failed to fetch open positions: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Leverage / margin
    # ------------------------------------------------------------------

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set the leverage for *symbol*."""
        try:
            return self._client.futures_change_leverage(
                symbol=symbol, leverage=leverage
            )
        except BinanceAPIException as exc:
            logger.warning("Could not set leverage for %s: %s", symbol, exc)
            raise

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict:
        """Place a market order on Binance Futures.

        Parameters
        ----------
        symbol:
            E.g. ``'BTCUSDT'``.
        side:
            ``'BUY'`` or ``'SELL'``.
        quantity:
            Order size in base currency (already rounded to step size by the
            caller).

        Returns
        -------
        dict
            The raw order response from Binance.
        """
        try:
            order = self._client.futures_create_order(
                symbol=symbol,
                side=side.upper(),
                type="MARKET",
                quantity=quantity,
            )
            logger.info(
                "Placed %s %s order: qty=%.6f, orderId=%s",
                side.upper(),
                symbol,
                quantity,
                order.get("orderId"),
            )
            return order
        except BinanceAPIException as exc:
            logger.error("Order failed (%s %s qty=%.6f): %s", side, symbol, quantity, exc)
            raise

    def close_position(self, symbol: str, position_amt: float) -> dict:
        """Close an open Futures position by placing the opposite market order."""
        side = "SELL" if position_amt > 0 else "BUY"
        quantity = abs(position_amt)
        return self.place_market_order(symbol, side, quantity)

    # ------------------------------------------------------------------
    # Symbol info helpers (step size for rounding)
    # ------------------------------------------------------------------

    def get_quantity_precision(self, symbol: str) -> int:
        """Return the number of decimal places allowed for *symbol* quantities."""
        info = self._client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == symbol:
                return int(s.get("quantityPrecision", 3))
        return 3
