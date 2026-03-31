# Copycat – Binance Copy-Trading Bot

Automatically mirrors the best-performing traders from the **Binance Futures Leaderboard** onto your own Binance Futures account.  
Positions are scaled to your bankroll and only executed on pairs that Binance actively supports.

---

## Features

| Feature | Details |
|---|---|
| **Signal Discovery** | Queries Binance's public Futures Leaderboard to find top traders by ROI |
| **Pair Validation** | Only mirrors trades on pairs that Binance Futures currently supports |
| **Trade Scaling** | Scales each position to a configurable fraction of your USDT balance × leverage |
| **Position Mirroring** | Opens and closes positions as leaders enter/exit trades |
| **Portfolio Cap** | Limits the number of concurrently open mirrored positions |
| **Testnet Support** | Safe to run against Binance Testnet before going live |
| **Extensible** | Pluggable `SignalSource` interface lets you add other platforms (eToro, etc.) |

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/codenimar/copycat.git
cd copycat
pip install -r requirements.txt
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and fill in your Binance API key/secret
```

Key settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `BINANCE_API_KEY` | – | Your Binance API key |
| `BINANCE_API_SECRET` | – | Your Binance API secret |
| `BINANCE_TESTNET` | `true` | Use Binance Futures Testnet |
| `MAX_POSITION_SIZE` | `0.05` | Max fraction of balance per trade (5 %) |
| `MAX_OPEN_POSITIONS` | `10` | Max concurrent mirrored positions |
| `FUTURES_LEVERAGE` | `5` | Leverage applied to every position |
| `SYNC_INTERVAL` | `60` | Seconds between sync cycles |
| `LEADERBOARD_TOP_N` | `5` | Number of top traders to follow |
| `LEADERBOARD_MIN_ROI` | `50.0` | Minimum ROI (%) to qualify |
| `LEADERBOARD_MIN_DAYS` | `30` | Minimum days active to qualify |
| `LEADERBOARD_PERIOD` | `MONTHLY` | Ranking period (DAILY/WEEKLY/MONTHLY/ALL_TIME) |

### 3. Run

```bash
python main.py
```

Or via the installed console script:

```bash
copycat
```

---

## Architecture

```
src/copycat/
├── __init__.py
├── config.py              – Environment-driven settings with validation
├── binance_client.py      – Binance Futures API wrapper (symbols, orders, balance)
├── signal_sources/
│   ├── base.py            – Abstract SignalSource, TradeSignal, TraderSignal dataclasses
│   └── binance_leaderboard.py  – Concrete source using Binance's public leaderboard API
├── portfolio.py           – In-memory tracker for mirrored positions
├── trader.py              – Trade-scaling formula + order execution
└── bot.py                 – Orchestration loop (run_once / run)
```

### Trade Scaling Formula

```
notional_usdt = MAX_POSITION_SIZE × balance × FUTURES_LEVERAGE
quantity      = floor(notional_usdt / mark_price, symbol_precision)
```

This ensures we never commit more than the configured fraction of our balance to any single position.

---

## Testing

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

All external calls (Binance API, leaderboard HTTP) are mocked.  The test suite covers:

- Config validation
- `TradeSignal` / `TraderSignal` dataclasses
- Leaderboard API parsing (ROI filtering, day filtering, short/long detection)
- Portfolio cap, duplicate detection, case-insensitive symbol lookup
- Trade scaling arithmetic (`_round_down`, `_calculate_quantity`)
- Full bot orchestration (open, close, skip, error paths)

---

## Disclaimer

> **This software is for educational purposes only.**  
> Trading cryptocurrencies involves significant financial risk.  
> Past performance of copy-traded accounts does not guarantee future results.  
> Always test thoroughly on the Binance Testnet before using real funds.  
> The authors accept no responsibility for financial losses.
