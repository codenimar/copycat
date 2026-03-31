"""Binance Leaderboard signal source.

Uses Binance's public leaderboard API to discover top-performing traders,
then fetches their open Futures positions so we can mirror them.

Endpoints used
--------------
* Leaderboard rankings:
  ``POST /bapi/futures/v3/public/future/leaderboard/searchLeaderboard``
* Trader base info:
  ``POST /bapi/futures/v3/public/future/leaderboard/getOtherLeaderboardBaseInfo``
* Trader open positions:
  ``POST /bapi/futures/v3/public/future/leaderboard/getOtherPosition``

These are the same calls the Binance web UI makes when you browse
https://www.binance.com/en/futures-activity/leaderboard – they are
publicly accessible without authentication.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from .base import SignalSource, TradeSignal, TraderSignal

logger = logging.getLogger(__name__)

_BASE = "https://www.binance.com/bapi/futures/v3/public/future/leaderboard"
_SEARCH_URL = f"{_BASE}/searchLeaderboard"
_BASE_INFO_URL = f"{_BASE}/getOtherLeaderboardBaseInfo"
_POSITION_URL = f"{_BASE}/getOtherPosition"

# Maps our internal period names to Binance API values
_PERIOD_MAP = {
    "DAILY": "DAILY",
    "WEEKLY": "WEEKLY",
    "MONTHLY": "MONTHLY",
    "ALL_TIME": "ALL",
}


def _post(url: str, payload: dict, timeout: int = 10) -> dict:
    """POST *payload* to *url* and return the parsed JSON response."""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


class BinanceLeaderboardSource(SignalSource):
    """Discovers top traders via Binance's public Futures Leaderboard API."""

    @property
    def name(self) -> str:
        return "Binance Leaderboard"

    def fetch_top_traders(
        self,
        top_n: int = 5,
        min_roi: float = 50.0,
        min_days: int = 30,
        period: str = "MONTHLY",
    ) -> list[TraderSignal]:
        """Return up to *top_n* traders meeting the ROI/days filters."""
        binance_period = _PERIOD_MAP.get(period.upper(), "MONTHLY")

        payload = {
            "isShared": True,
            "isTrader": True,
            "periodType": binance_period,
            "statisticsType": "ROI",
        }

        try:
            data = _post(_SEARCH_URL, payload)
        except requests.RequestException as exc:
            logger.error("Leaderboard fetch failed: %s", exc)
            return []

        rows: list[dict] = data.get("data", []) or []

        traders: list[TraderSignal] = []
        for row in rows:
            roi = float(row.get("roi", 0) or 0) * 100  # API returns a fraction
            pnl = float(row.get("pnl", 0) or 0)
            days = int(row.get("periodDurationInDay", 0) or 0)
            followers = int(row.get("followerCount", 0) or 0)
            trader_id = row.get("encryptedUid", "")
            nickname = row.get("nickName", trader_id)

            if roi < min_roi:
                continue
            if days < min_days:
                continue

            traders.append(
                TraderSignal(
                    trader_id=trader_id,
                    nickname=nickname,
                    roi=roi,
                    pnl=pnl,
                    followers=followers,
                    days_active=days,
                    extra=row,
                )
            )

            if len(traders) >= top_n:
                break

        logger.info(
            "Leaderboard returned %d qualifying traders (period=%s, min_roi=%.1f%%)",
            len(traders),
            period,
            min_roi,
        )
        return traders

    def fetch_positions(self, trader: TraderSignal) -> list[TradeSignal]:
        """Fetch and return the open Futures positions for *trader*."""
        payload = {
            "encryptedUid": trader.trader_id,
            "tradeType": "PERPETUAL",
        }

        try:
            data = _post(_POSITION_URL, payload)
        except requests.RequestException as exc:
            logger.warning(
                "Could not fetch positions for %s (%s): %s",
                trader.nickname,
                trader.trader_id,
                exc,
            )
            return []

        raw_positions: list[dict] = (data.get("data") or {}).get("otherPositionRetList", [])

        signals: list[TradeSignal] = []
        for pos in raw_positions:
            symbol = (pos.get("symbol") or "").upper()
            side = "LONG" if float(pos.get("amount", 0)) > 0 else "SHORT"
            entry_price = float(pos.get("entryPrice", 0) or 0)
            mark_price = float(pos.get("markPrice", 0) or 0)
            leverage = int(pos.get("leverage", 1) or 1)
            amount = abs(float(pos.get("amount", 0) or 0))

            if not symbol or entry_price <= 0 or amount <= 0:
                continue

            signals.append(
                TradeSignal(
                    symbol=symbol,
                    side=side,
                    entry_price=entry_price,
                    mark_price=mark_price,
                    leverage=leverage,
                    amount=amount,
                    source_trader_id=trader.trader_id,
                    extra=pos,
                )
            )

        logger.debug(
            "Trader %s has %d open position(s).", trader.nickname, len(signals)
        )
        return signals
