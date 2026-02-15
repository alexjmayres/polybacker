"""Copy Trading Engine.

Monitors wallet addresses on Polymarket and automatically mirrors their trades.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from py_clob_client.order_builder.constants import BUY, SELL

from polybacker.client import PolymarketClient
from polybacker.config import Settings
from polybacker import db

logger = logging.getLogger(__name__)


class CopyTrader:
    """Watches followed traders and copies their trades."""

    def __init__(
        self,
        settings: Settings,
        client: PolymarketClient,
        dry_run: bool = False,
    ):
        self.settings = settings
        self.client = client
        self.dry_run = dry_run
        self.db_path = settings.db_path
        self._running = False

        # Ensure DB is initialized
        db.init_db(self.db_path)

    # -------------------------------------------------------------------------
    # Trader management
    # -------------------------------------------------------------------------

    def load_traders_from_file(self, filepath: str = "traders.txt") -> int:
        """Load trader addresses from a text file into the DB.

        Returns the number of new traders added.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Traders file not found: {filepath}")
            return 0

        added = 0
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("0x") and len(line) == 42:
                if db.add_trader(self.db_path, line):
                    added += 1
                    logger.info(f"Added trader: {line}")
            else:
                logger.warning(f"Skipping invalid address: {line}")

        return added

    def get_traders(self) -> list[dict]:
        """Get all active followed traders."""
        return db.get_active_traders(self.db_path)

    # -------------------------------------------------------------------------
    # Trade evaluation
    # -------------------------------------------------------------------------

    def _parse_trade_time(self, trade: dict) -> Optional[datetime]:
        """Parse the timestamp from a trade record."""
        ts = trade.get("timestamp") or trade.get("created_at") or trade.get("time")
        if not ts:
            return None
        try:
            # Handle various formats
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            ts_str = str(ts).replace("Z", "+00:00")
            return datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return None

    def _get_trade_id(self, trade: dict) -> str:
        """Extract a unique trade identifier."""
        # Try various ID fields the API might return
        return str(
            trade.get("id")
            or trade.get("trade_id")
            or trade.get("transaction_hash")
            or f"{trade.get('asset_id', '')}_{trade.get('timestamp', '')}"
        )

    def should_copy(self, trade: dict, trader_address: str) -> tuple[bool, str]:
        """Determine if we should copy this trade.

        Returns:
            (should_copy: bool, reason: str)
        """
        trade_id = self._get_trade_id(trade)

        # 1. Already seen?
        if db.is_trade_seen(self.db_path, trade_id):
            return False, "already_seen"

        # 2. Too old?
        trade_time = self._parse_trade_time(trade)
        if trade_time:
            now = datetime.now(timezone.utc)
            age_seconds = (now - trade_time).total_seconds()
            if age_seconds > self.settings.max_trade_age:
                # Mark as seen so we don't re-check
                db.mark_trade_seen(self.db_path, trade_id)
                return False, f"too_old ({age_seconds:.0f}s)"

        # 3. Has a token ID we can trade?
        token_id = trade.get("asset_id") or trade.get("token_id")
        if not token_id:
            db.mark_trade_seen(self.db_path, trade_id)
            return False, "no_token_id"

        # 4. Has a side?
        side = trade.get("side", "").upper()
        if side not in ("BUY", "SELL"):
            db.mark_trade_seen(self.db_path, trade_id)
            return False, f"invalid_side: {side}"

        # 5. Daily spend limit?
        daily_spend = db.get_daily_spend(self.db_path, strategy="copy")
        if daily_spend >= self.settings.max_daily_spend:
            return False, f"daily_limit_reached (${daily_spend:.2f})"

        return True, "ok"

    def calculate_copy_size(self, trade: dict) -> float:
        """Calculate the USDC amount to copy.

        Applies: percentage of original * min/max bounds * daily spend remaining.
        """
        # Estimate original trade size in USDC
        size = float(trade.get("size", 0) or 0)
        price = float(trade.get("price", 0) or 0)
        original_usd = size * price if price > 0 else size

        if original_usd <= 0:
            return self.settings.min_copy_size

        # Apply percentage
        copy_size = original_usd * self.settings.copy_percentage

        # Apply min/max
        copy_size = max(copy_size, self.settings.min_copy_size)
        copy_size = min(copy_size, self.settings.max_copy_size)

        # Don't exceed remaining daily budget
        daily_spend = db.get_daily_spend(self.db_path, strategy="copy")
        remaining = self.settings.max_daily_spend - daily_spend
        if copy_size > remaining:
            copy_size = remaining

        return round(copy_size, 2)

    # -------------------------------------------------------------------------
    # Trade execution
    # -------------------------------------------------------------------------

    def execute_copy(self, trade: dict, trader_address: str) -> bool:
        """Copy a single trade.

        Returns True if the trade was executed (or logged in dry-run).
        """
        trade_id = self._get_trade_id(trade)
        token_id = trade.get("asset_id") or trade.get("token_id")
        side = trade.get("side", "").upper()
        market = trade.get("market", "") or trade.get("title", "") or ""
        copy_size = self.calculate_copy_size(trade)

        if copy_size <= 0:
            logger.warning("Copy size is 0 — skipping")
            db.mark_trade_seen(self.db_path, trade_id)
            return False

        clob_side = BUY if side == "BUY" else SELL

        logger.info(
            f"{'[DRY RUN] ' if self.dry_run else ''}"
            f"Copying trade from {trader_address[:10]}... | "
            f"{side} ${copy_size:.2f} | {market[:50]}"
        )

        status = "dry_run"
        if not self.dry_run:
            result = self.client.place_market_order(
                token_id=token_id,
                amount=copy_size,
                side=clob_side,
            )
            status = "executed" if result else "failed"

        # Record in DB
        db.record_trade(
            db_path=self.db_path,
            strategy="copy",
            token_id=token_id,
            side=side,
            amount=copy_size,
            market=market,
            copied_from=trader_address.lower(),
            original_trade_id=trade_id,
            status=status,
        )

        # Update trader stats
        if status == "executed":
            db.update_trader_stats(self.db_path, trader_address, copy_size)

        # Mark as seen
        db.mark_trade_seen(self.db_path, trade_id)

        if status == "failed":
            logger.error(f"Failed to execute copy trade for {trade_id}")
            return False

        return True

    # -------------------------------------------------------------------------
    # Polling loop
    # -------------------------------------------------------------------------

    def poll_trader(self, address: str) -> int:
        """Check a single trader for new trades and copy them.

        Returns the number of trades copied.
        """
        trades = self.client.get_trader_trades(address, limit=10)
        copied = 0

        for trade in trades:
            should, reason = self.should_copy(trade, address)
            if should:
                if self.execute_copy(trade, address):
                    copied += 1
            elif reason != "already_seen":
                trade_id = self._get_trade_id(trade)
                logger.debug(f"Skipped {trade_id[:16]}... — {reason}")

        return copied

    def run(self):
        """Main loop: poll all followed traders, copy new trades, repeat."""
        self._running = True

        # Load traders from file on startup
        self.load_traders_from_file()

        traders = self.get_traders()
        if not traders:
            logger.error(
                "No traders to follow! Add addresses to traders.txt or use: "
                "polybacker copy --add-trader 0x..."
            )
            return

        logger.info(f"Starting copy trading — following {len(traders)} traders")
        logger.info(f"Copy size: {self.settings.copy_percentage * 100:.0f}% "
                     f"(${self.settings.min_copy_size}-${self.settings.max_copy_size})")
        logger.info(f"Daily limit: ${self.settings.max_daily_spend}")
        logger.info(f"Poll interval: {self.settings.poll_interval}s")
        if self.dry_run:
            logger.info("DRY RUN MODE — no real trades will be placed")
        logger.info("")

        iteration = 0
        try:
            while self._running:
                iteration += 1
                total_copied = 0

                for trader in traders:
                    if not self._running:
                        break
                    try:
                        copied = self.poll_trader(trader["address"])
                        total_copied += copied
                    except Exception as e:
                        logger.error(
                            f"Error polling {trader['address'][:10]}...: {e}"
                        )

                if total_copied > 0:
                    logger.info(f"Scan #{iteration}: copied {total_copied} trades")
                else:
                    logger.debug(f"Scan #{iteration}: no new trades")

                # Periodic stats
                if iteration % 20 == 0:
                    self._log_stats()
                    # Refresh trader list (in case new ones were added)
                    traders = self.get_traders()
                    # Cleanup old dedup entries
                    db.cleanup_old_seen_trades(self.db_path)

                time.sleep(self.settings.poll_interval)

        except KeyboardInterrupt:
            logger.info("\nStopping copy trader...")
        finally:
            self._running = False
            self._log_stats()

    def stop(self):
        """Signal the run loop to stop."""
        self._running = False

    def _log_stats(self):
        """Log current stats."""
        stats = db.get_copy_stats(self.db_path)
        daily = db.get_daily_spend(self.db_path, strategy="copy")
        traders = self.get_traders()

        logger.info(
            f"Stats: {stats['total_trades']} trades copied | "
            f"${stats['total_spent']:.2f} total spent | "
            f"{stats['failed_trades']} failed | "
            f"${daily:.2f} spent today | "
            f"{len(traders)} traders followed"
        )
