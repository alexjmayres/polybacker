"""Polymarket API client wrapper.

Wraps py-clob-client (CLOB API) and requests (Data API / Gamma API)
into a single coherent interface.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from polybacker.config import Settings

logger = logging.getLogger(__name__)

# Rate limiting: track last request time per host
_last_request: dict[str, float] = {}
_MIN_REQUEST_INTERVAL = 0.15  # 150ms between requests to same host


def _rate_limit(host: str):
    """Simple rate limiter — sleep if we're requesting too fast."""
    now = time.time()
    last = _last_request.get(host, 0)
    elapsed = now - last
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request[host] = time.time()


def _patch_clob_http_client(proxy_url: str = ""):
    """Patch py-clob-client's global httpx client with proxy and/or HTTP/1.1 support.

    Must be called BEFORE creating any ClobClient instances.
    """
    import httpx
    from py_clob_client.http_helpers import helpers as _helpers

    kwargs = {}
    if proxy_url:
        kwargs["proxy"] = proxy_url
        logger.info(f"Routing CLOB API through proxy: {proxy_url[:30]}...")

    # Try HTTP/2 first, fall back to HTTP/1.1 if it fails
    try:
        _helpers._http_client = httpx.Client(http2=True, **kwargs)
    except Exception:
        logger.warning("HTTP/2 init failed, falling back to HTTP/1.1")
        _helpers._http_client = httpx.Client(http2=False, **kwargs)


class PolymarketClient:
    """Unified Polymarket API client."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "User-Agent": "polybacker/0.1.0",
        })

        # Patch the global httpx client with proxy support BEFORE creating CLOB client
        _patch_clob_http_client(proxy_url=getattr(settings, "proxy_url", ""))

        # If we have a SOCKS5 proxy, also route our requests.Session through it
        proxy_url = getattr(settings, "proxy_url", "")
        if proxy_url:
            self._session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

        # Initialize CLOB client
        client_params = {
            "host": settings.clob_host,
            "key": settings.private_key,
            "chain_id": settings.chain_id,
            "signature_type": settings.signature_type,
        }
        if settings.funder:
            client_params["funder"] = settings.funder

        self.clob = ClobClient(**client_params)

        # Use explicit Builder API creds if provided, otherwise derive from key
        if settings.api_key and settings.api_secret and settings.api_passphrase:
            creds = ApiCreds(
                api_key=settings.api_key,
                api_secret=settings.api_secret,
                api_passphrase=settings.api_passphrase,
            )
            self.clob.set_api_creds(creds)
            logger.info("CLOB client initialized with Builder API credentials")
        else:
            self.clob.set_api_creds(self.clob.create_or_derive_api_creds())
            logger.info("CLOB client initialized with derived API credentials")

    # -------------------------------------------------------------------------
    # Data API — public endpoints for querying trades/positions by address
    # -------------------------------------------------------------------------

    def get_trader_trades(self, address: str, limit: int = 20) -> list[dict]:
        """Get recent trades for a specific wallet address.

        Uses: GET https://data-api.polymarket.com/trades?user={address}
        """
        _rate_limit(self.settings.data_host)
        try:
            url = f"{self.settings.data_host}/trades"
            params = {"user": address.lower(), "limit": limit}
            logger.debug(f"Fetching trades: {url}?user={address.lower()[:10]}...&limit={limit}")
            resp = self._session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                logger.debug(f"Got {len(data)} trades for {address[:10]}...")
                return data
            else:
                logger.warning(f"Unexpected response type for trades from {address[:10]}...: {type(data).__name__}")
                return []
        except requests.RequestException as e:
            logger.error(f"Error fetching trades for {address[:10]}...: {e}")
            return []

    def get_trader_positions(self, address: str) -> list[dict]:
        """Get current positions for a specific wallet address.

        Uses: GET https://data-api.polymarket.com/positions?user={address}
        """
        _rate_limit(self.settings.data_host)
        try:
            resp = self._session.get(
                f"{self.settings.data_host}/positions",
                params={"user": address.lower()},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as e:
            logger.error(f"Error fetching positions for {address[:10]}...: {e}")
            return []

    def get_market_holders(self, condition_id: str, limit: int = 50) -> list[dict]:
        """Get top holders for a market.

        Uses: GET https://data-api.polymarket.com/holders
        """
        _rate_limit(self.settings.data_host)
        try:
            resp = self._session.get(
                f"{self.settings.data_host}/holders",
                params={"market": condition_id, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as e:
            logger.error(f"Error fetching holders: {e}")
            return []

    # -------------------------------------------------------------------------
    # Gamma API — market discovery and metadata
    # -------------------------------------------------------------------------

    def get_active_markets(self, limit: int = 50) -> list[dict]:
        """Fetch active markets from Gamma API.

        Uses: GET https://gamma-api.polymarket.com/markets
        """
        _rate_limit(self.settings.gamma_host)
        try:
            resp = self._session.get(
                f"{self.settings.gamma_host}/markets",
                params={"limit": limit, "active": "true"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except requests.RequestException as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    def search_markets(self, query: str, limit: int = 20) -> list[dict]:
        """Search markets by keyword."""
        markets = self.get_active_markets(limit=100)
        query_lower = query.lower()
        return [
            m for m in markets
            if query_lower in m.get("question", "").lower()
            or query_lower in m.get("description", "").lower()
        ][:limit]

    # -------------------------------------------------------------------------
    # CLOB API — pricing, order books, trading
    # -------------------------------------------------------------------------

    def get_price(self, token_id: str, side: str = "BUY") -> Optional[float]:
        """Get current price for a token."""
        _rate_limit(self.settings.clob_host)
        try:
            price = self.clob.get_price(token_id, side)
            return float(price) if price is not None else None
        except Exception as e:
            logger.error(f"Error getting price for {token_id[:16]}...: {e}")
            return None

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token."""
        _rate_limit(self.settings.clob_host)
        try:
            mid = self.clob.get_midpoint(token_id)
            return float(mid) if mid is not None else None
        except Exception as e:
            logger.error(f"Error getting midpoint: {e}")
            return None

    def get_order_book(self, token_id: str) -> Optional[dict]:
        """Get order book for a token."""
        _rate_limit(self.settings.clob_host)
        try:
            return self.clob.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Error getting order book: {e}")
            return None

    def get_spread(self, token_id: str) -> Optional[dict]:
        """Get bid/ask spread for a token."""
        _rate_limit(self.settings.clob_host)
        try:
            return self.clob.get_spread(token_id)
        except Exception as e:
            logger.error(f"Error getting spread: {e}")
            return None

    def place_market_order(
        self,
        token_id: str,
        amount: float,
        side: str,
        order_type: OrderType = OrderType.FOK,
    ) -> Optional[dict]:
        """Place a market order.

        Args:
            token_id: The conditional token ID.
            amount: Amount in USDC.
            side: 'BUY' or 'SELL' (use constants from py_clob_client).
            order_type: FOK (fill-or-kill) or GTC (good-til-cancel).

        Returns:
            Order response dict, or None on failure.
        """
        _rate_limit(self.settings.clob_host)
        try:
            logger.info(f"Placing market order: {side} ${amount:.2f} of {token_id[:16]}... (type={order_type})")
            order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                order_type=order_type,
            )
            signed_order = self.clob.create_market_order(order_args)
            response = self.clob.post_order(signed_order, order_type)
            logger.info(f"Market order response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error placing market order ({side} ${amount:.2f}): {e}")
            return {"error": str(e)}

    def place_limit_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
    ) -> Optional[dict]:
        """Place a GTC limit order at a specific price.

        Args:
            token_id: The conditional token ID.
            price: Limit price (0.0001–0.9999).
            size: Number of shares (not USDC amount).
            side: BUY or SELL constant from py_clob_client.

        Returns:
            Order response dict, or None on failure.
        """
        _rate_limit(self.settings.clob_host)
        try:
            logger.info(
                f"Placing limit order: {side} {size:.2f} shares @ {price:.4f} "
                f"of {token_id[:16]}... (GTC)"
            )
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side,
            )
            signed_order = self.clob.create_order(order_args)
            response = self.clob.post_order(signed_order, OrderType.GTC)
            logger.info(f"Limit order response: {response}")
            return response
        except Exception as e:
            logger.error(f"Error placing limit order ({side} {size:.2f}@{price:.4f}): {e}")
            return {"error": str(e)}

    def get_balance_allowance(self, token_id: Optional[str] = None) -> Optional[dict]:
        """Get balance and allowance info."""
        try:
            if token_id:
                return self.clob.get_balance_allowance(token_id)
            return None
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return None
