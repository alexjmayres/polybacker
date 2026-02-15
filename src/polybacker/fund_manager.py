"""STF (Successful Trader Fund) Manager.

Manages curated funds of top traders. Copies trades proportionally
based on fund allocations and AUM. Updates NAV daily.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from py_clob_client.order_builder.constants import BUY, SELL

from polybacker.client import PolymarketClient
from polybacker.config import Settings
from polybacker import db

logger = logging.getLogger(__name__)


class FundManager:
    """Manages STF funds — copies trades from allocated traders proportional to AUM."""

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

        db.init_db(self.db_path)

    # -------------------------------------------------------------------------
    # Trade sizing
    # -------------------------------------------------------------------------

    def calculate_fund_copy_size(
        self, fund: dict, trader_weight: float, original_usd: float
    ) -> float:
        """Calculate trade size for a fund based on AUM and trader weight.

        Size = (fund AUM * trader weight * copy_percentage) bounded by min/max.
        """
        aum = fund.get("total_aum", 0)
        if aum <= 0:
            return 0

        # Proportional to AUM and trader weight
        copy_size = original_usd * self.settings.copy_percentage * trader_weight

        # Cap at a fraction of AUM (max 5% of AUM per trade)
        max_per_trade = aum * 0.05
        copy_size = min(copy_size, max_per_trade)

        # Apply global bounds
        copy_size = max(copy_size, self.settings.min_copy_size)
        copy_size = min(copy_size, self.settings.max_copy_size)

        return round(copy_size, 2)

    # -------------------------------------------------------------------------
    # Trade execution
    # -------------------------------------------------------------------------

    def execute_fund_trade(
        self,
        fund: dict,
        trade: dict,
        trader_address: str,
        weight: float,
    ) -> bool:
        """Execute a trade on behalf of a fund.

        Returns True if the trade was executed successfully.
        """
        token_id = trade.get("asset_id") or trade.get("token_id")
        side = trade.get("side", "").upper()
        market = trade.get("market", "") or trade.get("title", "") or ""

        # Estimate original size
        size = float(trade.get("size", 0) or 0)
        price = float(trade.get("price", 0) or 0)
        original_usd = size * price if price > 0 else size

        copy_size = self.calculate_fund_copy_size(fund, weight, original_usd)
        if copy_size <= 0:
            return False

        clob_side = BUY if side == "BUY" else SELL
        fund_name = fund.get("name", f"Fund#{fund['id']}")

        logger.info(
            f"{'[DRY RUN] ' if self.dry_run else ''}"
            f"[{fund_name}] Copying from {trader_address[:10]}... | "
            f"{side} ${copy_size:.2f} (w={weight:.0%}) | {market[:50]}"
        )

        status = "dry_run"
        if not self.dry_run:
            result = self.client.place_market_order(
                token_id=token_id,
                amount=copy_size,
                side=clob_side,
            )
            status = "executed" if result else "failed"

        # Record in main trades table
        trade_id_str = str(
            trade.get("id")
            or trade.get("trade_id")
            or f"{trade.get('asset_id', '')}_{trade.get('timestamp', '')}"
        )

        trade_record_id = db.record_trade(
            db_path=self.db_path,
            strategy="fund",
            token_id=token_id,
            side=side,
            amount=copy_size,
            market=market,
            copied_from=trader_address.lower(),
            original_trade_id=f"fund_{fund['id']}_{trade_id_str}",
            status=status,
            notes=f"Fund: {fund_name}",
        )

        # Record in fund_trades
        if trade_record_id:
            try:
                db.record_fund_trade(
                    self.db_path,
                    fund_id=fund["id"],
                    trade_id=trade_record_id,
                    trader_address=trader_address,
                    amount=copy_size,
                )
            except Exception as e:
                logger.warning(f"Failed to record fund trade: {e}")

        if status == "failed":
            logger.error(f"Failed fund trade for {fund_name}")
            return False

        return True

    # -------------------------------------------------------------------------
    # Fund NAV update
    # -------------------------------------------------------------------------

    def update_fund_nav(self, fund_id: int):
        """Recalculate and record the NAV for a fund.

        NAV = total_aum / total_shares (or 1.0 if no shares).
        Records daily performance snapshot.
        """
        fund = db.get_fund(self.db_path, fund_id)
        if not fund:
            return

        total_shares = fund["total_shares"]
        total_aum = fund["total_aum"]

        if total_shares <= 0:
            nav = 1.0
        else:
            nav = total_aum / total_shares

        # Get yesterday's NAV for daily return calculation
        perf_history = db.get_fund_performance(self.db_path, fund_id, days=2)
        if perf_history:
            prev_nav = perf_history[-1]["nav"]
            daily_return = ((nav - prev_nav) / prev_nav) * 100 if prev_nav > 0 else 0
        else:
            daily_return = 0

        # Cumulative return from initial NAV of 1.0
        cumulative_return = ((nav - 1.0) / 1.0) * 100

        try:
            db.record_fund_performance(
                self.db_path,
                fund_id=fund_id,
                nav=round(nav, 6),
                daily_return=round(daily_return, 4),
                cumulative_return=round(cumulative_return, 4),
            )
            logger.debug(f"Fund #{fund_id} NAV: ${nav:.4f} (daily: {daily_return:+.2f}%)")
        except Exception as e:
            logger.error(f"Failed to update NAV for fund #{fund_id}: {e}")

    # -------------------------------------------------------------------------
    # Polling loop
    # -------------------------------------------------------------------------

    def poll_fund_traders(self, fund: dict) -> int:
        """Poll all traders allocated to a fund and copy new trades.

        Returns number of trades copied.
        """
        allocations = db.get_fund_allocations(self.db_path, fund["id"])
        if not allocations:
            return 0

        copied = 0
        for alloc in allocations:
            trader_address = alloc["trader_address"]
            weight = alloc["weight"]

            try:
                trades = self.client.get_trader_trades(trader_address, limit=10)
            except Exception as e:
                logger.error(f"Error fetching trades for {trader_address[:10]}...: {e}")
                continue

            for trade in trades:
                trade_id = str(
                    trade.get("id")
                    or trade.get("trade_id")
                    or f"{trade.get('asset_id', '')}_{trade.get('timestamp', '')}"
                )

                # Dedup with fund-prefixed ID
                dedup_id = f"fund_{fund['id']}_{trade_id}"
                if db.is_trade_seen(self.db_path, dedup_id):
                    continue

                # Check trade age
                ts = trade.get("timestamp") or trade.get("created_at")
                if ts:
                    try:
                        if isinstance(ts, (int, float)):
                            trade_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                        else:
                            ts_str = str(ts).replace("Z", "+00:00")
                            trade_time = datetime.fromisoformat(ts_str)
                        age = (datetime.now(timezone.utc) - trade_time).total_seconds()
                        if age > self.settings.max_trade_age:
                            db.mark_trade_seen(self.db_path, dedup_id)
                            continue
                    except (ValueError, TypeError):
                        pass

                # Check has token + side
                token_id = trade.get("asset_id") or trade.get("token_id")
                side = trade.get("side", "").upper()
                if not token_id or side not in ("BUY", "SELL"):
                    db.mark_trade_seen(self.db_path, dedup_id)
                    continue

                if self.execute_fund_trade(fund, trade, trader_address, weight):
                    copied += 1

                db.mark_trade_seen(self.db_path, dedup_id)

        return copied

    def run(self):
        """Main loop: poll all fund-allocated traders, copy trades, update NAVs."""
        self._running = True

        funds = db.get_funds(self.db_path, active_only=True)
        if not funds:
            logger.warning("No active funds found")
            return

        logger.info(f"Fund manager started — managing {len(funds)} funds")
        if self.dry_run:
            logger.info("DRY RUN MODE — no real trades will be placed")

        for fund in funds:
            allocs = db.get_fund_allocations(self.db_path, fund["id"])
            logger.info(
                f"  [{fund['name']}] AUM: ${fund['total_aum']:.2f} | "
                f"{len(allocs)} traders allocated"
            )

        iteration = 0
        try:
            while self._running:
                iteration += 1
                total_copied = 0

                for fund in funds:
                    if not self._running:
                        break
                    try:
                        copied = self.poll_fund_traders(fund)
                        total_copied += copied
                    except Exception as e:
                        logger.error(f"Error polling fund '{fund['name']}': {e}")

                if total_copied > 0:
                    logger.info(f"Fund scan #{iteration}: copied {total_copied} trades")

                # Update NAVs periodically (every 10 iterations)
                if iteration % 10 == 0:
                    for fund in funds:
                        try:
                            self.update_fund_nav(fund["id"])
                        except Exception as e:
                            logger.error(f"NAV update error for fund #{fund['id']}: {e}")

                    # Refresh fund list
                    funds = db.get_funds(self.db_path, active_only=True)
                    db.cleanup_old_seen_trades(self.db_path)

                time.sleep(self.settings.poll_interval)

        except KeyboardInterrupt:
            logger.info("\nStopping fund manager...")
        finally:
            self._running = False
            # Final NAV update
            for fund in funds:
                try:
                    self.update_fund_nav(fund["id"])
                except Exception:
                    pass
            logger.info("Fund manager stopped")

    def stop(self):
        """Signal the run loop to stop."""
        self._running = False
