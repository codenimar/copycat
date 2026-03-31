"""Tests for copycat.config."""

import os
import pytest

# Ensure we can import from src/
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from copycat.config import Config


def test_defaults():
    """Config should provide sensible defaults without any env vars."""
    cfg = Config()
    assert cfg.max_position_size == 0.05
    assert cfg.max_open_positions == 10
    assert cfg.futures_leverage == 5
    assert cfg.sync_interval == 60
    assert cfg.leaderboard_top_n == 5
    assert cfg.leaderboard_min_roi == 50.0
    assert cfg.leaderboard_min_days == 30
    assert cfg.leaderboard_period == "MONTHLY"
    assert cfg.testnet is True  # safe default


def test_validate_position_size_zero():
    cfg = Config(max_position_size=0.0)
    with pytest.raises(ValueError, match="MAX_POSITION_SIZE"):
        cfg.validate()


def test_validate_position_size_above_one():
    cfg = Config(max_position_size=1.1)
    with pytest.raises(ValueError, match="MAX_POSITION_SIZE"):
        cfg.validate()


def test_validate_max_open_positions_zero():
    cfg = Config(max_open_positions=0)
    with pytest.raises(ValueError, match="MAX_OPEN_POSITIONS"):
        cfg.validate()


def test_validate_leverage_zero():
    cfg = Config(futures_leverage=0)
    with pytest.raises(ValueError, match="FUTURES_LEVERAGE"):
        cfg.validate()


def test_validate_leverage_above_125():
    cfg = Config(futures_leverage=126)
    with pytest.raises(ValueError, match="FUTURES_LEVERAGE"):
        cfg.validate()


def test_validate_invalid_period():
    cfg = Config(leaderboard_period="YEARLY")
    with pytest.raises(ValueError, match="LEADERBOARD_PERIOD"):
        cfg.validate()


def test_validate_passes_for_valid_config():
    cfg = Config(
        api_key="key",
        api_secret="secret",
        max_position_size=0.02,
        max_open_positions=5,
        futures_leverage=10,
        leaderboard_top_n=3,
        leaderboard_period="WEEKLY",
    )
    cfg.validate()  # should not raise


def test_env_var_override(monkeypatch):
    monkeypatch.setenv("MAX_POSITION_SIZE", "0.1")
    monkeypatch.setenv("FUTURES_LEVERAGE", "10")
    monkeypatch.setenv("LEADERBOARD_PERIOD", "WEEKLY")

    cfg = Config()
    assert cfg.max_position_size == pytest.approx(0.1)
    assert cfg.futures_leverage == 10
    assert cfg.leaderboard_period == "WEEKLY"
