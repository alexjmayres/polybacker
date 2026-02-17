"""Telegram notification module for Polybacker.

Sends alerts when followed traders make trades and when copy trades are executed.
Configure via environment variables:
    TELEGRAM_BOT_TOKEN - Bot token from @BotFather
    TELEGRAM_CHAT_ID   - Chat/group ID to send messages to
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from polybacker.config import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send trade notifications via Telegram Bot API."""

    def __init__(self, settings: Settings):
        self.bot_token = getattr(settings, "telegram_bot_token", "") or ""
        self.chat_id = getattr(settings, "telegram_chat_id", "") or ""
        self.enabled = bool(self.bot_token and self.chat_id)
        self._session = requests.Session()

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram Bot API."""
        if not self.enabled:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = self._session.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            if not resp.ok:
                logger.warning(f"Telegram send failed: {resp.status_code} {resp.text}")
                return False
            return True
        except Exception as e:
            logger.warning(f"Telegram send error: {e}")
            return False

    def send_trader_trade_alert(
        self,
        trader_address: str,
        trader_alias: str,
        side: str,
        market: str,
        size: float,
        price: float,
    ) -> bool:
        """Alert when a followed trader makes a trade."""
        emoji = "\U0001f7e2" if side == "BUY" else "\U0001f534"  # Green/Red circle
        usd = size * price if price > 0 else size
        msg = (
            f"{emoji} <b>TRADER TRADE DETECTED</b>\n\n"
            f"<b>Trader:</b> {trader_alias}\n"
            f"<code>{trader_address}</code>\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Market:</b> {market[:80]}\n"
            f"<b>Size:</b> {size:.2f} shares @ ${price:.4f}\n"
            f"<b>Value:</b> ${usd:.2f}\n"
        )
        return self._send_message(msg)

    def send_copy_trade_alert(
        self,
        trader_address: str,
        trader_alias: str,
        side: str,
        market: str,
        copy_size: float,
        price: float,
        order_mode: str = "MARKET",
        status: str = "executed",
    ) -> bool:
        """Alert when a copy trade is executed."""
        if status == "executed":
            emoji = "\u2705"  # checkmark
            status_text = "EXECUTED"
        elif status == "failed":
            emoji = "\u274c"  # X
            status_text = "FAILED"
        else:
            emoji = "\U0001f4dd"  # memo
            status_text = "DRY RUN"

        msg = (
            f"{emoji} <b>COPY TRADE {status_text}</b>\n\n"
            f"<b>Copying:</b> {trader_alias}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Market:</b> {market[:80]}\n"
            f"<b>Amount:</b> ${copy_size:.2f}\n"
            f"<b>Price:</b> ${price:.4f}\n"
            f"<b>Mode:</b> {order_mode}\n"
        )
        return self._send_message(msg)
