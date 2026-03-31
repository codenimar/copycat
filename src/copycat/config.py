"""Configuration loader.

All settings are read from environment variables (or a .env file).
Sensible defaults are provided so the bot can run without any extra setup
in test mode.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _get_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    # Binance credentials
    api_key: str = field(default_factory=lambda: os.getenv("BINANCE_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BINANCE_API_SECRET", ""))
    testnet: bool = field(default_factory=lambda: _get_bool("BINANCE_TESTNET", True))

    # Trade sizing
    max_position_size: float = field(
        default_factory=lambda: _get_float("MAX_POSITION_SIZE", 0.05)
    )
    max_open_positions: int = field(
        default_factory=lambda: _get_int("MAX_OPEN_POSITIONS", 10)
    )
    futures_leverage: int = field(
        default_factory=lambda: _get_int("FUTURES_LEVERAGE", 5)
    )
    sync_interval: int = field(
        default_factory=lambda: _get_int("SYNC_INTERVAL", 60)
    )

    # Leaderboard filters
    leaderboard_top_n: int = field(
        default_factory=lambda: _get_int("LEADERBOARD_TOP_N", 5)
    )
    leaderboard_min_roi: float = field(
        default_factory=lambda: _get_float("LEADERBOARD_MIN_ROI", 50.0)
    )
    leaderboard_min_days: int = field(
        default_factory=lambda: _get_int("LEADERBOARD_MIN_DAYS", 30)
    )
    leaderboard_period: str = field(
        default_factory=lambda: os.getenv("LEADERBOARD_PERIOD", "MONTHLY")
    )

    def validate(self) -> None:
        """Raise ValueError for obviously wrong settings."""
        if not (0 < self.max_position_size <= 1):
            raise ValueError("MAX_POSITION_SIZE must be between 0 (exclusive) and 1 (inclusive).")
        if self.max_open_positions < 1:
            raise ValueError("MAX_OPEN_POSITIONS must be at least 1.")
        if not (1 <= self.futures_leverage <= 125):
            raise ValueError("FUTURES_LEVERAGE must be between 1 and 125.")
        if self.leaderboard_top_n < 1:
            raise ValueError("LEADERBOARD_TOP_N must be at least 1.")
        valid_periods = {"DAILY", "WEEKLY", "MONTHLY", "ALL_TIME"}
        if self.leaderboard_period not in valid_periods:
            raise ValueError(
                f"LEADERBOARD_PERIOD must be one of {valid_periods}."
            )
