# Polybacker

Polymarket copy trading and arbitrage bot. Follow successful traders automatically without paying third-party fees.

## Quick Start

### 1. Install

```bash
cd Polybacker
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your Polymarket wallet private key
```

### 3. Add traders to follow

```bash
# From the Polymarket leaderboard (https://polymarket.com/leaderboard)
polybacker copy add 0x1234567890abcdef1234567890abcdef12345678

# Or add them to traders.txt (one address per line)
```

### 4. Run

```bash
# Copy trading (dry run first to verify)
polybacker copy start --dry-run

# Copy trading (live)
polybacker copy start

# Arbitrage scanner
polybacker arb --dry-run

# Web dashboard
polybacker server
# Open http://localhost:5000
```

## CLI Commands

```
polybacker copy start           Start copy trading bot
polybacker copy start --dry-run Monitor without placing trades
polybacker copy add ADDRESS     Follow a trader
polybacker copy remove ADDRESS  Unfollow a trader
polybacker copy list            Show followed traders
polybacker copy stats           Show copy trading stats
polybacker copy trades          Show recent copied trades

polybacker arb                  Start arbitrage scanner
polybacker arb --dry-run        Scan without trading

polybacker discover             Browse active markets
polybacker discover -s "trump"  Search markets

polybacker server               Start web dashboard
```

## Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `POLYMARKET_PRIVATE_KEY` | (required) | Wallet private key |
| `COPY_PERCENTAGE` | `0.10` | Copy 10% of their trade size |
| `MIN_COPY_SIZE` | `5.0` | Minimum $5 per copy |
| `MAX_COPY_SIZE` | `100.0` | Maximum $100 per copy |
| `MAX_DAILY_SPEND` | `500.0` | Safety limit per day |
| `POLL_INTERVAL` | `30` | Seconds between scans |
| `AUTO_EXECUTE` | `true` | Set `false` for monitoring only |

## Project Structure

```
src/polybacker/
  config.py          Settings from .env
  db.py              SQLite persistence
  client.py          Polymarket API wrapper
  copy_trader.py     Copy trading engine
  arbitrage.py       Arbitrage scanner
  market_discovery.py Market browser
  cli.py             CLI interface
  server.py          Flask dashboard API

server/static/
  dashboard.html     Web dashboard

docs/               Reference documentation
archive/            Original generated files
```

## How Copy Trading Works

1. You add wallet addresses of successful Polymarket traders
2. The bot polls the Polymarket Data API every 30s for their recent trades
3. When a new trade is detected, it calculates your copy size (percentage of theirs, bounded by min/max)
4. The order is placed via the CLOB API using your wallet
5. Everything is logged to SQLite for tracking

## Requirements

- Python 3.11+
- Polymarket wallet with USDC on Polygon
- Token allowances set (run `archive/setup_allowances.py` once)
