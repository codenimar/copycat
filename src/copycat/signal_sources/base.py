"""Abstract base classes for signal sources.

A *SignalSource* discovers the best traders on some platform and returns
their current open positions as :class:`TradeSignal` objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TradeSignal:
    """A single open position held by a leader trader.

    Attributes
    ----------
    symbol:
        Trading pair, e.g. ``'BTCUSDT'``.
    side:
        ``'LONG'`` or ``'SHORT'``.
    entry_price:
        Average entry price of the leader's position.
    mark_price:
        Current mark price (used to size our order).
    leverage:
        Leverage the leader is using (informational; we use our own config).
    amount:
        Notional size (in USDT) of the leader's position.  Used as a
        relative weight when scaling to our bankroll.
    source_trader_id:
        Unique identifier of the trader on the source platform.
    """

    symbol: str
    side: str  # 'LONG' | 'SHORT'
    entry_price: float
    mark_price: float
    leverage: int
    amount: float  # notional USDT
    source_trader_id: str
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.side = self.side.upper()
        if self.side not in ("LONG", "SHORT"):
            raise ValueError(f"side must be 'LONG' or 'SHORT', got {self.side!r}")
        self.symbol = self.symbol.upper()


@dataclass
class TraderSignal:
    """Performance metrics for a single leader trader.

    Attributes
    ----------
    trader_id:
        Platform-specific unique identifier.
    nickname:
        Display name.
    roi:
        Return-on-investment as a percentage (e.g. ``150.0`` = 150 %).
    pnl:
        Realised profit-and-loss in USDT.
    followers:
        Number of followers on the platform.
    days_active:
        How many days the account has been tracked.
    positions:
        The trader's current open positions.
    """

    trader_id: str
    nickname: str
    roi: float
    pnl: float
    followers: int
    days_active: int
    positions: list[TradeSignal] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


class SignalSource(ABC):
    """Interface every signal provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the signal source."""

    @abstractmethod
    def fetch_top_traders(
        self,
        top_n: int,
        min_roi: float,
        min_days: int,
        period: str,
    ) -> list[TraderSignal]:
        """Return the top *top_n* traders ranked by ROI.

        Parameters
        ----------
        top_n:
            Maximum number of traders to return.
        min_roi:
            Minimum ROI (%) required to be included.
        min_days:
            Minimum days active required.
        period:
            Ranking window: ``'DAILY'``, ``'WEEKLY'``, ``'MONTHLY'``,
            or ``'ALL_TIME'``.
        """

    @abstractmethod
    def fetch_positions(self, trader: TraderSignal) -> list[TradeSignal]:
        """Return the current open positions for *trader*."""
