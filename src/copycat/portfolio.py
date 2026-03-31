"""Portfolio manager – tracks which leader positions we are currently mirroring.

The portfolio is stored entirely in-memory.  For persistence across restarts
you would serialise ``Portfolio.positions`` to a file or database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MirroredPosition:
    """A leader position that we have opened on our account.

    Attributes
    ----------
    symbol:
        Trading pair, e.g. ``'BTCUSDT'``.
    side:
        ``'LONG'`` or ``'SHORT'``.
    quantity:
        Size of our open position in base currency.
    entry_price:
        Price at which we entered.
    leader_trader_id:
        Trader ID on the source platform.
    order_id:
        Binance order ID returned when the position was opened.
    """

    symbol: str
    side: str
    quantity: float
    entry_price: float
    leader_trader_id: str
    order_id: Optional[str] = None


class Portfolio:
    """Tracks open mirrored positions and enforces limits."""

    def __init__(self, max_open_positions: int = 10) -> None:
        self._max = max_open_positions
        # key: (symbol, leader_trader_id) → MirroredPosition
        self.positions: dict[tuple[str, str], MirroredPosition] = {}

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_open(self, symbol: str, leader_trader_id: str) -> bool:
        """Return True if we already mirror this leader/symbol pair."""
        return (symbol.upper(), leader_trader_id) in self.positions

    def can_open_new(self) -> bool:
        """Return True if we have room for another position."""
        return len(self.positions) < self._max

    def open_count(self) -> int:
        """Return the number of currently mirrored positions."""
        return len(self.positions)

    def all_positions(self) -> list[MirroredPosition]:
        return list(self.positions.values())

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(self, position: MirroredPosition) -> None:
        """Record a newly opened mirrored position."""
        key = (position.symbol.upper(), position.leader_trader_id)
        self.positions[key] = position
        logger.info(
            "Portfolio: added %s %s (qty=%.6f, leader=%s)",
            position.side,
            position.symbol,
            position.quantity,
            position.leader_trader_id,
        )

    def remove(self, symbol: str, leader_trader_id: str) -> Optional[MirroredPosition]:
        """Remove a closed position from tracking.  Returns it, or None."""
        key = (symbol.upper(), leader_trader_id)
        pos = self.positions.pop(key, None)
        if pos:
            logger.info(
                "Portfolio: removed %s %s (leader=%s)",
                pos.side,
                pos.symbol,
                leader_trader_id,
            )
        return pos
