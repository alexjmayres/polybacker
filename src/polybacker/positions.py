"""Position Tracker.

Maintains open position state from trade records and updates
current prices from Polymarket for live P&L tracking.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from polybacker.client import PolymarketClient
from polybacker.config import Settings
from polybacker import db

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks open positions and updates live prices for P&L calculation."""

    def __init__(
        self,
        settings: Settings,
        client: PolymarketClient,
    ):
        self.settings = settings
        self.client = client
        self.db_path = settings.db_path
        self._running = False

        db.init_db(self.db_path)

    # -------------------------------------------------------------------------
    # Trade recording — called by CopyTrader / ArbitrageScanner after execution
    # -------------------------------------------------------------------------

    def record_trade(
        self,
        user_address: str,
        token_id: str,
        market: str,
        side: str,
        amount: float,
        price: float,
        strategy: str = "",
        copied_from: str = "",
    ):
        """Record a trade and update the corresponding position.

        Called after trade execution to keep position state in sync.
        """
        if price <= 0:
            logger.debug(f"Skipping position update — no price for {token_id[:16]}")
            return

        try:
            db.upsert_position(
                db_path=self.db_path,
                user_address=user_address,
                token_id=token_id,
                market=market,
                side=side,
                trade_amount=amount,
                trade_price=price,
                strategy=strategy,
                copied_from=copied_from,
            )
            logger.debug(f"Position updated: {side} ${amount:.2f} @ ${price:.4f}")
        except Exception as e:
            logger.error(f"Failed to update position: {e}")

    # -------------------------------------------------------------------------
    # Price updates
    # -------------------------------------------------------------------------

    def update_prices(self, user_address: Optional[str] = None):
        """Fetch current prices for all open positions and update P&L.

        For each open position, queries the Polymarket CLOB for the
        current midpoint price and recalculates unrealized P&L.
        """
        positions = db.get_open_positions(self.db_path, user_address=user_address)

        if not positions:
            return

        updates = []
        for pos in positions:
            token_id = pos["token_id"]
            try:
                # Get midpoint price (average of bid/ask)
                price = self.client.get_midpoint(token_id)
                if price is None:
                    # Fallback to BUY price
                    price = self.client.get_price(token_id, side="BUY")

                if price is not None and price > 0:
                    updates.append({
                        "id": pos["id"],
                        "current_price": float(price),
                    })
            except Exception as e:
                logger.debug(f"Could not fetch price for {token_id[:16]}...: {e}")

        if updates:
            try:
                db.update_position_prices(self.db_path, updates)
                logger.debug(f"Updated prices for {len(updates)} positions")
            except Exception as e:
                logger.error(f"Failed to batch update position prices: {e}")

    # -------------------------------------------------------------------------
    # Sync from existing trades (backfill on startup)
    # -------------------------------------------------------------------------

    def sync_from_trades(self, user_address: Optional[str] = None):
        """Backfill positions from the trades table.

        Scans all executed trades and builds/updates position state.
        Useful on first startup or to repair position data.
        """
        trades = db.get_trades(
            self.db_path,
            limit=10000,
            user_address=user_address,
        )

        # Process trades oldest-first
        trades.reverse()

        synced = 0
        for trade in trades:
            if trade.get("status") != "executed":
                continue

            price = trade.get("price", 0) or 0
            if price <= 0:
                continue

            try:
                db.upsert_position(
                    db_path=self.db_path,
                    user_address=trade.get("user_address", "legacy"),
                    token_id=trade["token_id"],
                    market=trade.get("market", ""),
                    side=trade["side"],
                    trade_amount=trade["amount"],
                    trade_price=price,
                    strategy=trade.get("strategy", ""),
                    copied_from=trade.get("copied_from", ""),
                )
                synced += 1
            except Exception as e:
                logger.debug(f"Sync skip: {e}")

        logger.info(f"Position sync complete: processed {synced} trades")

    # -------------------------------------------------------------------------
    # Background price updater loop
    # -------------------------------------------------------------------------

    def run(self, interval: int = 30):
        """Background loop that periodically updates position prices.

        Args:
            interval: Seconds between price update cycles.
        """
        self._running = True
        logger.info(f"Position tracker started — updating every {interval}s")

        try:
            while self._running:
                try:
                    self.update_prices()
                except Exception as e:
                    logger.error(f"Position price update error: {e}")

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Position tracker stopping...")
        finally:
            self._running = False
            logger.info("Position tracker stopped")

    def stop(self):
        """Signal the price update loop to stop."""
        self._running = False
