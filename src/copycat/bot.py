"""Main bot orchestration loop.

The :class:`CopycatBot` ties together all components:

* Fetches top traders from the configured signal source.
* Opens mirrored positions for their active trades.
* Closes positions the leader has already exited.
* Repeats at a configurable interval.

Usage
-----
Run the bot from the command line::

    python main.py

Or import and drive it programmatically::

    bot = CopycatBot()
    bot.run_once()  # single sync cycle
    bot.run()       # infinite loop
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .binance_client import BinanceClient
from .config import Config
from .portfolio import Portfolio
from .signal_sources.base import SignalSource, TraderSignal
from .signal_sources.binance_leaderboard import BinanceLeaderboardSource
from .trader import Trader

logger = logging.getLogger(__name__)


class CopycatBot:
    """Copy-trading bot that mirrors Binance Leaderboard traders."""

    def __init__(
        self,
        config: Optional[Config] = None,
        signal_source: Optional[SignalSource] = None,
    ) -> None:
        self.config = config or Config()
        self.config.validate()

        self._client = BinanceClient(self.config)
        self._portfolio = Portfolio(self.config.max_open_positions)
        self._trader = Trader(self._client, self._portfolio, self.config)
        self._source: SignalSource = signal_source or BinanceLeaderboardSource()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the copy-trading loop indefinitely (blocks)."""
        logger.info(
            "CopycatBot started. Source=%s, testnet=%s, sync every %ds.",
            self._source.name,
            self.config.testnet,
            self.config.sync_interval,
        )
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected error in sync cycle: %s", exc, exc_info=True)
            time.sleep(self.config.sync_interval)

    def run_once(self) -> dict:
        """Execute one sync cycle.

        Returns a summary dict with counts of opened/closed positions.
        """
        summary = {"opened": 0, "closed": 0, "skipped": 0, "errors": 0}

        # --- Fetch current account balance --------------------------------
        try:
            balance = self._client.get_futures_balance()
        except Exception as exc:
            logger.error("Cannot fetch balance – aborting cycle: %s", exc)
            return summary

        logger.info("Available USDT balance: %.2f", balance)

        # --- Discover top traders -----------------------------------------
        traders = self._source.fetch_top_traders(
            top_n=self.config.leaderboard_top_n,
            min_roi=self.config.leaderboard_min_roi,
            min_days=self.config.leaderboard_min_days,
            period=self.config.leaderboard_period,
        )

        if not traders:
            logger.info("No qualifying traders found this cycle.")
            return summary

        # --- Gather desired positions from leaders ------------------------
        desired: dict[tuple[str, str], object] = {}  # (symbol, trader_id) → signal
        for trader in traders:
            signals = self._source.fetch_positions(trader)
            for sig in signals:
                desired[(sig.symbol, sig.source_trader_id)] = sig

        # --- Close positions the leader has exited ------------------------
        for (symbol, trader_id), pos in list(self._portfolio.positions.items()):
            if (symbol, trader_id) not in desired:
                closed = self._trader.close_position(symbol, trader_id)
                if closed:
                    summary["closed"] += 1
                else:
                    summary["errors"] += 1

        # --- Open new positions -------------------------------------------
        for (symbol, trader_id), sig in desired.items():
            if self._portfolio.is_open(symbol, trader_id):
                continue
            opened = self._trader.open_position(sig, balance)
            if opened:
                summary["opened"] += 1
            else:
                summary["skipped"] += 1

        logger.info(
            "Cycle complete: opened=%d, closed=%d, skipped=%d, errors=%d",
            summary["opened"],
            summary["closed"],
            summary["skipped"],
            summary["errors"],
        )
        return summary


def main() -> None:
    """Entry point for the ``copycat`` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    bot = CopycatBot()
    bot.run()


if __name__ == "__main__":
    main()
