"""Arbitrage Scanner & Executor.

Detects risk-free arbitrage opportunities on Polymarket where
YES + NO token prices sum to less than $1.00.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from polybacker.client import PolymarketClient
from polybacker.config import Settings
from polybacker import db

logger = logging.getLogger(__name__)


class ArbitrageScanner:
    """Scans Polymarket for arbitrage opportunities and executes trades."""

    def __init__(
        self,
        settings: Settings,
        client: PolymarketClient,
        dry_run: bool = False,
        user_address: str = "",
    ):
        self.settings = settings
        self.client = client
        self.dry_run = dry_run
        self.user_address = user_address
        self.db_path = settings.db_path
        self._running = False

        db.init_db(self.db_path)

    def check_opportunity(
        self, yes_token_id: str, no_token_id: str
    ) -> dict | None:
        """Check if an arbitrage opportunity exists for a YES/NO pair.

        If YES_price + NO_price < 1.00, buying both guarantees a profit
        since one will always resolve to $1.00 at settlement.

        Returns opportunity dict or None.
        """
        yes_price = self.client.get_price(yes_token_id, side="BUY")
        no_price = self.client.get_price(no_token_id, side="BUY")

        if yes_price is None or no_price is None:
            return None

        combined_cost = yes_price + no_price
        if combined_cost >= 1.0 or combined_cost <= 0:
            return None

        profit = 1.0 - combined_cost
        profit_pct = (profit / combined_cost) * 100

        if profit_pct < self.settings.min_profit_pct:
            return None

        return {
            "yes_token": yes_token_id,
            "no_token": no_token_id,
            "yes_price": yes_price,
            "no_price": no_price,
            "combined_cost": combined_cost,
            "profit": profit,
            "profit_pct": profit_pct,
        }

    def execute_arbitrage(self, opportunity: dict, market_name: str = "") -> bool:
        """Execute an arbitrage trade — buy both YES and NO tokens.

        Returns True if both legs executed successfully.
        """
        amount = min(self.settings.trade_amount, self.settings.max_position_size)
        expected_profit = opportunity["profit"] * amount

        # Split amount proportionally between YES and NO
        yes_amount = amount * (opportunity["yes_price"] / opportunity["combined_cost"])
        no_amount = amount * (opportunity["no_price"] / opportunity["combined_cost"])

        logger.info(
            f"{'[DRY RUN] ' if self.dry_run else ''}"
            f"Arbitrage: YES=${opportunity['yes_price']:.4f} + "
            f"NO=${opportunity['no_price']:.4f} = "
            f"${opportunity['combined_cost']:.4f} | "
            f"Profit: {opportunity['profit_pct']:.2f}%"
        )

        if self.dry_run:
            # Record as dry run
            for token_id, side_amount, label in [
                (opportunity["yes_token"], yes_amount, "YES"),
                (opportunity["no_token"], no_amount, "NO"),
            ]:
                db.record_trade(
                    db_path=self.db_path,
                    strategy="arbitrage",
                    token_id=token_id,
                    side="BUY",
                    amount=side_amount,
                    market=f"{market_name} ({label})",
                    price=opportunity[f"{label.lower()}_price"],
                    expected_profit=expected_profit / 2,
                    status="dry_run",
                    user_address=self.user_address,
                )
            return True

        # Execute both legs
        from py_clob_client.order_builder.constants import BUY

        yes_result = self.client.place_market_order(
            token_id=opportunity["yes_token"],
            amount=yes_amount,
            side=BUY,
        )
        no_result = self.client.place_market_order(
            token_id=opportunity["no_token"],
            amount=no_amount,
            side=BUY,
        )

        def _leg_ok(result: object) -> bool:
            """True only if the order succeeded (not None, not an error dict)."""
            if result is None:
                return False
            if isinstance(result, dict) and "error" in result:
                return False
            return True

        yes_ok = _leg_ok(yes_result)
        no_ok = _leg_ok(no_result)
        success = yes_ok and no_ok

        # Record trades
        for token_id, side_amount, label, ok, result in [
            (opportunity["yes_token"], yes_amount, "YES", yes_ok, yes_result),
            (opportunity["no_token"], no_amount, "NO", no_ok, no_result),
        ]:
            fail_reason = ""
            if not ok:
                if isinstance(result, dict) and "error" in result:
                    fail_reason = result["error"]
                else:
                    fail_reason = "Order execution failed"
            db.record_trade(
                db_path=self.db_path,
                strategy="arbitrage",
                token_id=token_id,
                side="BUY",
                amount=side_amount,
                market=f"{market_name} ({label})",
                price=opportunity[f"{label.lower()}_price"],
                expected_profit=expected_profit / 2,
                status="executed" if ok else "failed",
                notes="" if ok else fail_reason,
                user_address=self.user_address,
            )

        if not success:
            logger.error(
                f"Partial arbitrage execution — "
                f"YES: {'OK' if yes_ok else 'FAILED'}, "
                f"NO: {'OK' if no_ok else 'FAILED'}"
            )

        return success

    def scan_markets(self, markets: list[dict]) -> list[dict]:
        """Scan a list of markets for arbitrage opportunities.

        Returns list of opportunity dicts.
        """
        opportunities = []

        for market in markets:
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                continue

            yes_token = tokens[0].get("token_id")
            no_token = tokens[1].get("token_id")
            if not yes_token or not no_token:
                continue

            opp = self.check_opportunity(yes_token, no_token)
            if opp:
                opp["market"] = market.get("question", "Unknown")
                opportunities.append(opp)

        return opportunities

    def run(self):
        """Main loop: fetch markets, scan for arbitrage, execute, repeat."""
        self._running = True

        logger.info("Fetching active markets...")
        markets = self.client.get_active_markets(limit=50)

        valid_markets = [m for m in markets if len(m.get("tokens", [])) >= 2]
        logger.info(f"Monitoring {len(valid_markets)} markets")

        if not valid_markets:
            logger.error("No valid markets found. Check your connection.")
            return

        iteration = 0
        try:
            while self._running:
                iteration += 1
                opportunities = self.scan_markets(valid_markets)

                if opportunities:
                    for opp in opportunities:
                        logger.info(
                            f"Opportunity: {opp['market'][:50]} — "
                            f"{opp['profit_pct']:.2f}% profit"
                        )
                        if self.settings.auto_execute or self.dry_run:
                            self.execute_arbitrage(opp, opp["market"])

                if iteration % 10 == 0:
                    stats = db.get_arb_stats(self.db_path)
                    logger.info(
                        f"Arb stats: {stats['total_trades']} trades | "
                        f"${stats['total_expected_profit']:.2f} expected profit"
                    )
                    # Refresh markets periodically
                    markets = self.client.get_active_markets(limit=50)
                    valid_markets = [m for m in markets if len(m.get("tokens", [])) >= 2]

                time.sleep(self.settings.poll_interval)

        except KeyboardInterrupt:
            logger.info("\nStopping arbitrage scanner...")
        finally:
            self._running = False
            stats = db.get_arb_stats(self.db_path)
            logger.info(
                f"Final stats: {stats['total_trades']} trades | "
                f"${stats['total_expected_profit']:.2f} expected profit"
            )

    def stop(self):
        """Signal the run loop to stop."""
        self._running = False
