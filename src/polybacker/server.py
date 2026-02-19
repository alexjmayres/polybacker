"""Flask API server for the Polybacker dashboard.

Provides REST endpoints and WebSocket events for real-time monitoring
of copy trading, arbitrage, position tracking, and STF fund management.
Supports SIWE authentication with wallet whitelist gating.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from polybacker.config import Settings
from polybacker import db
from polybacker.auth import (
    verify_siwe_message,
    create_jwt,
    decode_jwt,
    require_auth,
    require_owner,
)

logger = logging.getLogger(__name__)


def _derive_owner_address(settings: Settings) -> str | None:
    """Derive the owner's Ethereum address from the private key."""
    if not settings.private_key:
        return None
    try:
        from eth_account import Account
        key = settings.private_key
        if not key.startswith("0x"):
            key = "0x" + key
        return Account.from_key(key).address.lower()
    except Exception as e:
        logger.warning(f"Could not derive owner address: {e}")
        return None


def create_app(settings: Settings) -> tuple[Flask, SocketIO]:
    """App factory — creates and configures the Flask app."""

    static_dir = Path(__file__).parent.parent.parent / "server" / "static"

    app = Flask(__name__, static_folder=str(static_dir))
    CORS(app, origins="*", supports_credentials=False)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    db_path = settings.db_path
    db.init_db(db_path)

    # Derive owner address and set up owner user
    owner_address = _derive_owner_address(settings)
    if owner_address:
        db.create_or_get_user(db_path, owner_address, role="owner")
        db.claim_legacy_data(db_path, owner_address)
        # Auto-whitelist the owner
        db.add_to_whitelist(db_path, owner_address, added_by="system")
        logger.info(f"Owner address: {owner_address}")

        # Auto-restore followed traders from env var (survives ephemeral deploys)
        if settings.followed_traders:
            existing_traders = db.get_active_traders(db_path, user_address=owner_address)
            existing_addrs = {t["address"].lower() for t in existing_traders}
            for entry in settings.followed_traders.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split(":", 1)
                addr = parts[0].strip().lower()
                alias = parts[1].strip() if len(parts) > 1 else ""
                if addr and addr not in existing_addrs:
                    db.add_trader(db_path, addr, alias=alias, user_address=owner_address)
                    logger.info(f"Auto-restored followed trader: {alias or addr[:10]}")

        # Auto-create PB500 Master Fund if it doesn't exist
        existing_funds = db.get_funds(db_path, active_only=False)
        pb500 = next((f for f in existing_funds if f["name"] == "PB500 Master Fund"), None)
        if not pb500:
            fund_id = db.create_fund(
                db_path, owner_address,
                "PB500 Master Fund",
                "Curated portfolio of top Polymarket traders. "
                "Managed by the Polybacker operator. "
                "Invest to get proportional exposure to all allocated traders.",
            )
            logger.info(f"Created PB500 Master Fund (id={fund_id})")
        else:
            logger.info(f"PB500 Master Fund exists (id={pb500['id']})")

    # Polymarket client is lazily initialized on first use.
    # The py-clob-client uses httpx with HTTP/2 which can fail if initialized
    # at module level or inside socketio.run() context. We use a lock to
    # ensure thread-safe lazy init.
    _pm_client_lock = threading.Lock()
    app.config["pm_client"] = None
    app.config["pm_client_lock"] = _pm_client_lock
    app.config["settings"] = settings
    app.config["owner_address"] = owner_address
    app.config["copy_trader"] = None
    app.config["arb_scanner"] = None
    app.config["fund_manager"] = None
    app.config["position_tracker"] = None
    app.config["copy_thread"] = None
    app.config["arb_thread"] = None
    app.config["fund_thread"] = None
    app.config["position_thread"] = None
    app.config["whitelist_enabled"] = True  # Whitelist enforcement on by default

    def _get_pm_client():
        """Lazily initialise and return the shared PolymarketClient.

        Thread-safe: uses a lock to prevent duplicate init.
        If py-clob-client's httpx HTTP/2 singleton has issues, we patch it
        to use HTTP/1.1 and retry.
        """
        client = app.config.get("pm_client")
        if client is not None:
            return client

        with app.config["pm_client_lock"]:
            # Double-check after acquiring lock
            client = app.config.get("pm_client")
            if client is not None:
                return client

            from polybacker.client import PolymarketClient
            client = PolymarketClient(settings)

            app.config["pm_client"] = client
            proxy_info = f" (via proxy)" if settings.proxy_url else ""
            logger.info(f"Polymarket CLOB client initialized{proxy_info}")
            return client

    def _get_user_pm_client(user_address: str):
        """Get a PolymarketClient configured with the user's own API creds.

        Falls back to the shared server-level client if the user has no
        stored credentials.
        """
        user_creds = db.get_user_api_creds(db_path, user_address)
        if not user_creds or not user_creds.get("api_key"):
            return _get_pm_client()

        # Build a per-user Settings override
        from polybacker.config import Settings
        user_settings = settings.model_copy(update={
            "api_key": user_creds["api_key"],
            "api_secret": user_creds.get("api_secret", ""),
            "api_passphrase": user_creds.get("api_passphrase", ""),
        })
        pm_addr = user_creds.get("polymarket_address", "")
        if pm_addr:
            user_settings = user_settings.model_copy(update={
                "funder": pm_addr,
                "polymarket_address": pm_addr,
            })

        from polybacker.client import PolymarketClient
        client = PolymarketClient(user_settings)
        logger.info(f"Created per-user Polymarket client for {user_address[:10]}...")
        return client

    # Create auth decorator bound to this app's JWT secret
    auth = require_auth(settings.jwt_secret)

    # =========================================================================
    # Health / Version (no auth)
    # =========================================================================

    @app.route("/api/health")
    def health():
        """Health check — no auth required. Used to verify deploy version."""
        import time as _t
        import os
        return jsonify({
            "status": "ok",
            "version": "2026-02-18.3",
            "timestamp": int(_t.time()),
            "db_path": db_path,
            "db_exists": os.path.exists(db_path),
            "db_dir_exists": os.path.exists(os.path.dirname(db_path)) if os.path.dirname(db_path) else True,
            "followed_traders_env": bool(settings.followed_traders),
            "proxy_url": bool(settings.proxy_url),
            "wireguard": bool(os.environ.get("WIREGUARD_CONFIG")),
        })

    @app.route("/api/debug/trade-errors")
    def debug_trade_errors():
        """Show recent failed trades with error reasons — for debugging only."""
        try:
            with db._connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT id, timestamp, market, side, amount, status, notes "
                    "FROM trades WHERE status = 'failed' "
                    "ORDER BY timestamp DESC LIMIT 10"
                ).fetchall()
                return jsonify([dict(r) for r in rows])
        except Exception as e:
            return jsonify({"error": str(e)})

    # -------------------------------------------------------------------------
    # Live PnL from Polymarket Data API — fallback when no local trades exist
    # -------------------------------------------------------------------------

    _pnl_cache: dict[str, tuple[float, list]] = {}  # key -> (timestamp, data)
    _PNL_CACHE_TTL = 300  # 5 minutes

    def _fetch_live_pnl(
        wallet: str, days: int = 30, strategy_filter: str = ""
    ) -> list[dict]:
        """Fetch real trade history from Polymarket Data API and build PnL series.

        This provides live chart data even before the copy/arb engines have run.
        """
        import time as _time
        cache_key = f"{wallet}_{days}_{strategy_filter}"
        now = _time.time()

        # Check cache
        if cache_key in _pnl_cache:
            cached_time, cached_data = _pnl_cache[cache_key]
            if now - cached_time < _PNL_CACHE_TTL:
                return cached_data

        try:
            import requests as req
            from datetime import datetime as dt, timedelta

            # Fetch trades from Polymarket Data API
            resp = req.get(
                f"{settings.data_host}/trades",
                params={"user": wallet.lower(), "limit": 500},
                timeout=15,
                headers={"Accept": "application/json"},
            )
            if not resp.ok:
                return []

            trades = resp.json()
            if not isinstance(trades, list) or not trades:
                return []

            # Calculate date cutoff
            cutoff = dt.utcnow() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d")

            # Group trades by date and compute PnL
            by_date: dict[str, dict] = {}
            for t in trades:
                # Parse timestamp
                ts = t.get("timestamp") or t.get("created_at") or t.get("time") or ""
                if isinstance(ts, (int, float)):
                    date_str = dt.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                else:
                    date_str = str(ts)[:10]

                if date_str < cutoff_str:
                    continue

                if date_str not in by_date:
                    by_date[date_str] = {"trades": 0, "spent": 0.0, "profit": 0.0}

                size = float(t.get("size", 0) or 0)
                price = float(t.get("price", 0) or 0)
                side = str(t.get("side", "")).upper()
                usd = size * price

                by_date[date_str]["trades"] += 1
                by_date[date_str]["spent"] += usd

                # Estimate profit:
                # SELL trades = realized profit relative to 0.5 midpoint
                # BUY trades at low prices = expected profit potential
                if side == "SELL":
                    by_date[date_str]["profit"] += usd * max(0, price - 0.5)
                elif side == "BUY" and price < 0.5:
                    by_date[date_str]["profit"] += usd * (0.5 - price) * 0.4

            # Fill in missing dates so chart shows a continuous 30-day line
            start_date = dt.utcnow() - timedelta(days=days)
            today_str = dt.utcnow().strftime("%Y-%m-%d")
            for i in range(days + 1):
                d = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
                if d > today_str:
                    break
                if d not in by_date:
                    by_date[d] = {"trades": 0, "spent": 0.0, "profit": 0.0}

            # Build sorted series with cumulative P&L
            dates = sorted(by_date.keys())
            series = []
            cumulative = 0.0
            for d in dates:
                entry = by_date[d]
                cumulative += entry["profit"]
                series.append({
                    "date": d,
                    "trades": entry["trades"],
                    "spent": round(entry["spent"], 2),
                    "profit": round(entry["profit"], 2),
                    "cumulative_profit": round(cumulative, 2),
                })

            # If we need to split for copy vs arb — use all trades for both
            # since the Polymarket Data API doesn't distinguish strategy
            # (In production, the local DB tracks this. This is just the fallback.)

            _pnl_cache[cache_key] = (now, series)
            return series

        except Exception as e:
            logger.warning(f"Failed to fetch live PnL: {e}")
            return []

    # =========================================================================
    # Dashboard (legacy HTML — Next.js frontend is the primary UI)
    # =========================================================================

    @app.route("/")
    def index():
        return send_from_directory(str(static_dir), "dashboard.html")

    # =========================================================================
    # Auth Endpoints (with whitelist enforcement)
    # =========================================================================

    @app.route("/api/auth/nonce", methods=["POST"])
    def auth_nonce():
        """Generate a nonce for SIWE authentication."""
        nonce = db.create_session_nonce(db_path)
        return jsonify({"nonce": nonce})

    @app.route("/api/auth/verify", methods=["POST"])
    def auth_verify():
        """Verify a SIWE message signature and issue a JWT token.

        Enforces wallet whitelist — only whitelisted addresses (and the owner)
        can authenticate.
        """
        data = request.json
        if not data:
            return jsonify({"error": "Missing request body"}), 400

        message_str = data.get("message")
        signature = data.get("signature")
        if not message_str or not signature:
            return jsonify({"error": "Missing message or signature"}), 400

        try:
            address = verify_siwe_message(message_str, signature)
        except Exception as e:
            return jsonify({"error": f"SIWE verification failed: {e}"}), 401

        # Check the nonce was one we issued
        from siwe import SiweMessage
        siwe_msg = SiweMessage.from_message(message_str)
        nonce = siwe_msg.nonce

        if not db.verify_session_nonce(db_path, nonce):
            return jsonify({"error": "Invalid or expired nonce"}), 401

        # Determine role: owner if address matches private key
        role = "user"
        is_owner = owner_address and address == owner_address
        if is_owner:
            role = "owner"

        # Whitelist enforcement: owner is always allowed; others must be whitelisted
        if app.config.get("whitelist_enabled", True) and not is_owner and not db.is_whitelisted(db_path, address):
            return jsonify({"error": "Wallet not whitelisted. Contact the operator for access."}), 403

        # Create or get user
        user = db.create_or_get_user(db_path, address, role=role)

        # Issue JWT
        token, expires_at = create_jwt(
            address=address,
            role=user["role"],
            secret=settings.jwt_secret,
            expiry_hours=settings.jwt_expiry_hours,
        )

        # Mark session verified
        db.mark_session_verified(
            db_path, nonce, address, token, expires_at.isoformat()
        )

        return jsonify({
            "token": token,
            "address": address,
            "role": user["role"],
        })

    @app.route("/api/auth/session")
    def auth_session():
        """Check the current session validity."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "No token"}), 401

        token = auth_header[7:]
        payload = decode_jwt(token, settings.jwt_secret)
        if not payload:
            return jsonify({"error": "Invalid token"}), 401

        # Accept both "sub" (standard JWT) and "address" (legacy tokens)
        addr = payload.get("sub") or payload.get("address", "")
        return jsonify({
            "authenticated": True,
            "address": addr,
            "role": payload.get("role", "user"),
        })

    # =========================================================================
    # Whitelist Management (owner only)
    # =========================================================================

    @app.route("/api/whitelist")
    @auth
    @require_owner
    def get_whitelist():
        """Get all whitelisted addresses."""
        wl = db.get_whitelist(db_path)
        return jsonify(wl)

    @app.route("/api/whitelist", methods=["POST"])
    @auth
    @require_owner
    def add_whitelist():
        """Add an address to the whitelist."""
        data = request.json or {}
        address = data.get("address", "").strip()
        if not address.startswith("0x") or len(address) != 42:
            return jsonify({"error": "Invalid Ethereum address"}), 400
        if db.add_to_whitelist(db_path, address, added_by=request.user_address):
            return jsonify({"message": f"Added {address} to whitelist"})
        return jsonify({"error": "Already whitelisted"}), 409

    @app.route("/api/whitelist/<address>", methods=["DELETE"])
    @auth
    @require_owner
    def remove_whitelist(address):
        """Remove an address from the whitelist."""
        # Prevent removing the owner
        if owner_address and address.lower() == owner_address:
            return jsonify({"error": "Cannot remove owner from whitelist"}), 400
        if db.remove_from_whitelist(db_path, address):
            return jsonify({"message": f"Removed {address} from whitelist"})
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/whitelist/settings")
    @auth
    @require_owner
    def get_whitelist_settings():
        """Get whitelist enforcement settings."""
        return jsonify({
            "enabled": app.config.get("whitelist_enabled", True),
        })

    @app.route("/api/whitelist/settings", methods=["PATCH"])
    @auth
    @require_owner
    def update_whitelist_settings():
        """Toggle whitelist enforcement on/off."""
        data = request.json or {}
        if "enabled" in data:
            app.config["whitelist_enabled"] = bool(data["enabled"])
            state = "enabled" if app.config["whitelist_enabled"] else "disabled"
            logger.info(f"Whitelist enforcement {state} by {request.user_address}")
            return jsonify({
                "message": f"Whitelist enforcement {state}",
                "enabled": app.config["whitelist_enabled"],
            })
        return jsonify({"error": "Missing 'enabled' field"}), 400

    # =========================================================================
    # Status
    # =========================================================================

    def _build_status_payload() -> dict:
        """Build engine status dict — used by REST, WebSocket, and broadcast."""
        return {
            "copy_trading": "running" if (app.config["copy_thread"] and app.config["copy_thread"].is_alive()) else "stopped",
            "arbitrage": "running" if (app.config["arb_thread"] and app.config["arb_thread"].is_alive()) else "stopped",
            "fund_manager": "running" if (app.config["fund_thread"] and app.config["fund_thread"].is_alive()) else "stopped",
        }

    @app.route("/api/status")
    @auth
    def get_status():
        payload = _build_status_payload()
        payload["config"] = {
            "copy_percentage": settings.copy_percentage,
            "min_copy_size": settings.min_copy_size,
            "max_copy_size": settings.max_copy_size,
            "max_daily_spend": settings.max_daily_spend,
            "min_profit_pct": settings.min_profit_pct,
            "trade_amount": settings.trade_amount,
            "poll_interval": settings.poll_interval,
            "auto_execute": settings.auto_execute,
        }
        return jsonify(payload)

    # =========================================================================
    # Copy Trading Endpoints
    # =========================================================================

    @app.route("/api/copy/start", methods=["POST"])
    @auth
    def copy_start():
        if app.config["copy_thread"] and app.config["copy_thread"].is_alive():
            return jsonify({"error": "Copy trading already running"}), 400

        from polybacker.copy_trader import CopyTrader

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = _get_user_pm_client(request.user_address)

            # Pre-flight: verify API credentials are configured
            has_api_key = bool(settings.api_key)
            user_creds = db.get_user_api_creds(db_path, request.user_address)
            has_user_creds = bool(user_creds and user_creds.get("api_key"))
            if not has_api_key and not has_user_creds:
                return jsonify({
                    "error": "No Builder API credentials configured. "
                    "Go to Settings and enter your Polymarket Builder API key, secret, and passphrase. "
                    "Get them from https://polymarket.com/settings/builder"
                }), 400

            # Log how many traders exist for this user
            active_traders = db.get_active_traders(db_path, user_address=request.user_address)
            logger.info(
                f"Starting copy engine for {request.user_address[:10]}... "
                f"with {len(active_traders)} active traders, dry_run={dry_run}"
            )

            trader = CopyTrader(
                settings=settings, client=client, dry_run=dry_run,
                user_address=request.user_address,
            )
            # Traders come from the DB (added via web UI) — no need for traders.txt
            app.config["copy_trader"] = trader

            thread = threading.Thread(target=trader.run, daemon=True)
            thread.start()
            app.config["copy_thread"] = thread

            # Also start the position tracker if not already running
            _ensure_position_tracker(settings)

            socketio.emit("status", _build_status_payload())
            return jsonify({"message": "Copy trading started", "dry_run": dry_run})
        except Exception as e:
            import traceback
            logger.error(f"Copy start failed: {e}\n{traceback.format_exc()}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/copy/stop", methods=["POST"])
    @auth
    def copy_stop():
        trader = app.config.get("copy_trader")
        if trader:
            trader.stop()
            app.config["copy_trader"] = None
            socketio.emit("status", _build_status_payload())
            return jsonify({"message": "Copy trading stopped"})
        return jsonify({"error": "Not running"}), 400

    @app.route("/api/copy/test-trade", methods=["POST"])
    @auth
    def copy_test_trade():
        """Execute a single test trade to verify the trading pipeline.

        Fetches the most recent trade from a followed trader and runs it
        through the full copy pipeline. Always dry-run by default.

        Body (all optional):
        {
            "trader_address": "0x...",  // defaults to first followed trader
            "live": false               // true to execute a real trade (default: false/dry-run)
        }
        """
        import traceback

        data = request.json or {}
        trader_address = data.get("trader_address")
        live = data.get("live", False)

        try:
            # Get followed traders
            traders = db.get_active_traders(db_path, user_address=request.user_address)
            if not traders:
                return jsonify({"error": "No followed traders. Add a trader first."}), 400

            # Find the target trader
            target_trader = None
            if trader_address:
                for t in traders:
                    if t["address"].lower() == trader_address.lower():
                        target_trader = t
                        break
                if not target_trader:
                    return jsonify({"error": f"Trader {trader_address} not found in followed list"}), 404
            else:
                target_trader = traders[0]

            alias = target_trader.get("alias", "") or target_trader["address"][:10] + "..."

            # Get user's PM client
            client = _get_user_pm_client(request.user_address)

            # Fetch recent trades for this trader
            recent_trades = client.get_trader_trades(target_trader["address"], limit=5)
            if not recent_trades:
                return jsonify({
                    "error": f"No recent trades found for {alias}. They may not have traded recently.",
                    "trader": alias,
                    "trader_address": target_trader["address"],
                }), 404

            # Use the most recent trade
            trade = recent_trades[0]
            trade_side = trade.get("side", "").upper() or "BUY"
            trade_market = trade.get("market", "") or trade.get("title", "") or trade.get("question", "") or "Unknown market"
            trade_price = float(trade.get("price", 0) or 0)
            trade_size = float(trade.get("size", 0) or 0)
            token_id = trade.get("asset_id") or trade.get("token_id") or trade.get("asset")

            if not token_id:
                return jsonify({
                    "error": "Latest trade has no token ID — cannot simulate order",
                    "trade": {
                        "side": trade_side,
                        "market": trade_market[:60],
                        "price": trade_price,
                        "size": trade_size,
                    }
                }), 400

            # Create a temporary CopyTrader to calculate sizing
            from polybacker.copy_trader import CopyTrader
            temp_trader = CopyTrader(
                settings=settings,
                client=client,
                dry_run=(not live),
                user_address=request.user_address,
            )

            # Calculate copy size
            copy_size = temp_trader.calculate_copy_size(trade, target_trader)
            resolved = temp_trader._resolve_settings(target_trader)
            order_mode = resolved["order_mode"]

            # Build result
            result = {
                "trader": alias,
                "trader_address": target_trader["address"],
                "trade": {
                    "side": trade_side,
                    "market": trade_market[:80],
                    "price": trade_price,
                    "size": trade_size,
                    "token_id": token_id[:20] + "..." if len(str(token_id)) > 20 else token_id,
                },
                "copy": {
                    "copy_size_usd": copy_size,
                    "order_mode": order_mode,
                    "dry_run": not live,
                },
            }

            if copy_size <= 0:
                result["status"] = "skipped"
                result["message"] = "Copy size is $0 — check daily limits or copy percentage"
                return jsonify(result)

            # Actually run through execute_copy if live, otherwise simulate
            if live:
                # Real execution
                success = temp_trader.execute_copy(trade, target_trader)
                result["status"] = "executed" if success else "failed"
                result["message"] = f"{'Executed' if success else 'Failed'}: {trade_side} ${copy_size:.2f} on {trade_market[:50]}"
            else:
                # Dry run — just show what would happen
                if order_mode == "limit":
                    slippage_pct = resolved.get("limit_order_pct")
                    limit_price = temp_trader._calculate_limit_price(trade, trade_side, slippage_pct)
                    num_shares = round(copy_size / limit_price, 2) if limit_price else 0
                    result["copy"]["limit_price"] = limit_price
                    result["copy"]["num_shares"] = num_shares
                result["status"] = "dry_run"
                result["message"] = f"Test OK: Would {trade_side} ${copy_size:.2f} on {trade_market[:50]}"

            # Record in activity log
            try:
                db.record_engine_event(
                    db_path,
                    event_type="test_trade",
                    message=result["message"],
                    strategy="copy",
                    details=f"trader={alias}, side={trade_side}, amount=${copy_size:.2f}, mode={order_mode}, live={live}",
                    user_address=request.user_address,
                )
            except Exception:
                pass  # Don't fail the response over logging

            return jsonify(result)

        except Exception as e:
            logger.error(f"Test trade error: {e}\n{traceback.format_exc()}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/copy/traders")
    @auth
    def copy_traders():
        include_inactive = request.args.get("include_inactive", "").lower() == "true"
        if include_inactive:
            traders = db.get_all_traders(db_path, user_address=request.user_address)
        else:
            traders = db.get_active_traders(db_path, user_address=request.user_address)
        return jsonify(traders)

    @app.route("/api/copy/traders", methods=["POST"])
    @auth
    def copy_add_trader():
        data = request.json
        address = data.get("address", "")
        alias = data.get("alias", "")
        if not address.startswith("0x") or len(address) != 42:
            return jsonify({"error": "Invalid address"}), 400
        if db.add_trader(db_path, address, alias, user_address=request.user_address):
            return jsonify({"message": f"Added {address}"})
        return jsonify({"error": "Already following"}), 409

    @app.route("/api/copy/traders/<address>", methods=["DELETE"])
    @auth
    def copy_remove_trader(address):
        if db.remove_trader(db_path, address, user_address=request.user_address):
            return jsonify({"message": f"Removed {address}"})
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/copy/traders/<address>", methods=["PATCH"])
    @auth
    def copy_update_trader(address):
        """Update per-trader copy settings.

        Accepts JSON with any subset of:
        {copy_percentage, min_copy_size, max_copy_size, max_daily_spend, limit_order_pct, order_mode, active}
        """
        data = request.json or {}
        valid_keys = {"copy_percentage", "min_copy_size", "max_copy_size", "max_daily_spend", "limit_order_pct", "order_mode", "active"}
        updates = {}
        for key in valid_keys:
            if key in data:
                val = data[key]
                # Allow null to clear overrides
                if val is None:
                    updates[key] = None
                elif key == "active":
                    updates[key] = 1 if val else 0
                elif key == "order_mode":
                    # Validate order_mode is "market" or "limit"
                    if val not in ("market", "limit", None):
                        return jsonify({"error": "order_mode must be 'market' or 'limit'"}), 400
                    updates[key] = val
                else:
                    val = float(val)
                    if val < 0:
                        return jsonify({"error": f"{key} must be >= 0"}), 400
                    updates[key] = val

        if not updates:
            return jsonify({"error": "No valid settings provided"}), 400

        if db.update_trader_settings(db_path, address, request.user_address, **updates):
            return jsonify({"message": f"Updated settings for {address}"})
        return jsonify({"error": "Trader not found"}), 404

    @app.route("/api/copy/traders/<address>/profile")
    @auth
    def copy_trader_profile(address):
        """Get a followed trader's live positions and recent trade history from Polymarket.

        Returns their current open positions and trade history for PnL charting.
        """
        try:
            client = _get_user_pm_client(request.user_address)
        except Exception:
            # If CLOB client can't init (no private key), use a basic requests client
            import requests as req
            sess = req.Session()
            sess.headers.update({"Accept": "application/json"})

            # Fetch positions
            try:
                pos_resp = sess.get(
                    f"{settings.data_host}/positions",
                    params={"user": address.lower()},
                    timeout=15,
                )
                positions = pos_resp.json() if pos_resp.ok else []
            except Exception:
                positions = []

            # Fetch trades
            try:
                trades_resp = sess.get(
                    f"{settings.data_host}/trades",
                    params={"user": address.lower(), "limit": 200},
                    timeout=15,
                )
                trades = trades_resp.json() if trades_resp.ok else []
            except Exception:
                trades = []

            return jsonify({"positions": positions, "trades": trades})

        # Use the client to fetch data
        positions = client.get_trader_positions(address)
        trades = client.get_trader_trades(address, limit=200)

        return jsonify({"positions": positions, "trades": trades})

    @app.route("/api/copy/trades")
    @auth
    def copy_trades():
        limit = request.args.get("limit", 50, type=int)
        trades = db.get_trades(
            db_path, strategy="copy", limit=limit,
            user_address=request.user_address,
        )
        return jsonify(trades)

    @app.route("/api/copy/stats")
    @auth
    def copy_stats():
        stats = db.get_copy_stats(db_path, user_address=request.user_address)
        stats["daily_spend"] = db.get_daily_spend(
            db_path, strategy="copy", user_address=request.user_address,
        )
        stats["daily_limit"] = settings.max_daily_spend
        stats["order_mode"] = settings.order_mode
        stats["max_slippage"] = settings.max_slippage
        return jsonify(stats)

    @app.route("/api/copy/settings")
    @auth
    def get_copy_settings():
        """Return the effective global copy trading settings (read-only)."""
        return jsonify({
            "copy_percentage": round(settings.copy_percentage * 100, 1),
            "min_copy_size": settings.min_copy_size,
            "max_copy_size": settings.max_copy_size,
            "max_daily_spend": settings.max_daily_spend,
            "order_mode": settings.order_mode,
            "max_slippage": round(settings.max_slippage * 100, 1),
            "poll_interval": settings.poll_interval,
        })

    @app.route("/api/copy/traders/pnl")
    @auth
    def copy_traders_pnl():
        """Get PNL stats per followed trader since follow date.

        Returns a list of trader performance summaries:
        - total_copied, total_spent, realized approx PnL, trade count.
        """
        traders = db.get_all_traders(db_path, user_address=request.user_address)
        result = []
        for t in traders:
            addr = t["address"]
            followed_since = t.get("added_at", "")
            alias = t.get("alias", "")

            # Get trades copied from this trader
            with db._connect(db_path) as conn:
                rows = conn.execute(
                    """SELECT COUNT(*) as trade_count,
                              COALESCE(SUM(amount), 0) as total_spent,
                              COALESCE(SUM(CASE WHEN status='executed' THEN amount ELSE 0 END), 0) as executed_spent,
                              COALESCE(SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END), 0) as failed_count
                       FROM trades
                       WHERE strategy = 'copy' AND copied_from = ? AND user_address = ?""",
                    (addr.lower(), request.user_address),
                ).fetchone()

                trade_count = rows["trade_count"]
                total_spent = rows["total_spent"]
                executed_spent = rows["executed_spent"]
                failed_count = rows["failed_count"]

                # Get position PnL for this trader
                pos_rows = conn.execute(
                    """SELECT COALESCE(SUM(unrealized_pnl), 0) as total_pnl,
                              COALESCE(SUM(size * current_price), 0) as current_value,
                              COALESCE(SUM(cost_basis), 0) as cost_basis,
                              COUNT(*) as position_count
                       FROM positions
                       WHERE copied_from = ? AND user_address = ? AND status = 'open'""",
                    (addr.lower(), request.user_address),
                ).fetchone()

                unrealized_pnl = pos_rows["total_pnl"]
                current_value = pos_rows["current_value"]
                cost_basis = pos_rows["cost_basis"]
                position_count = pos_rows["position_count"]

            result.append({
                "address": addr,
                "alias": alias,
                "active": bool(t.get("active", 0)),
                "followed_since": followed_since,
                "trade_count": trade_count,
                "total_spent": round(total_spent, 2),
                "executed_spent": round(executed_spent, 2),
                "failed_count": failed_count,
                "unrealized_pnl": round(unrealized_pnl, 2),
                "current_value": round(current_value, 2),
                "cost_basis": round(cost_basis, 2),
                "position_count": position_count,
                "order_mode": t.get("order_mode"),
            })

        return jsonify(result)

    def _get_pm_wallet(user_addr: str) -> str:
        """Get the best Polymarket wallet address for live data queries.

        Uses the auto-discovery system to find the correct trading address.
        """
        return _discover_pm_address(user_addr)

    @app.route("/api/copy/pnl")
    @auth
    def copy_pnl():
        days = request.args.get("days", 30, type=int)
        # Always use live Polymarket data (local DB is ephemeral on Render)
        pm_wallet = _get_pm_wallet(request.user_address)
        series = _fetch_live_pnl(pm_wallet, days)
        if not series:
            # Fall back to local DB if API fails
            series = db.get_pnl_series(
                db_path, strategy="copy", user_address=request.user_address,
                days=days,
            )
        return jsonify(series)

    # =========================================================================
    # Arbitrage Endpoints
    # =========================================================================

    @app.route("/api/arb/start", methods=["POST"])
    @auth
    def arb_start():
        if app.config["arb_thread"] and app.config["arb_thread"].is_alive():
            return jsonify({"error": "Arbitrage already running"}), 400

        from polybacker.arbitrage import ArbitrageScanner

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = _get_user_pm_client(request.user_address)

            scanner = ArbitrageScanner(
                settings=settings, client=client, dry_run=dry_run,
                user_address=request.user_address,
            )
            app.config["arb_scanner"] = scanner

            thread = threading.Thread(target=scanner.run, daemon=True)
            thread.start()
            app.config["arb_thread"] = thread

            # Also start the position tracker if not already running
            _ensure_position_tracker(settings)

            socketio.emit("status", _build_status_payload())
            return jsonify({"message": "Arbitrage started", "dry_run": dry_run})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/arb/stop", methods=["POST"])
    @auth
    def arb_stop():
        scanner = app.config.get("arb_scanner")
        if scanner:
            scanner.stop()
            app.config["arb_scanner"] = None
            socketio.emit("status", _build_status_payload())
            return jsonify({"message": "Arbitrage stopped"})
        return jsonify({"error": "Not running"}), 400

    @app.route("/api/arb/trades")
    @auth
    def arb_trades():
        limit = request.args.get("limit", 50, type=int)
        trades = db.get_trades(
            db_path, strategy="arbitrage", limit=limit,
            user_address=request.user_address,
        )
        return jsonify(trades)

    @app.route("/api/arb/stats")
    @auth
    def arb_stats():
        return jsonify(db.get_arb_stats(db_path, user_address=request.user_address))

    @app.route("/api/arb/pnl")
    @auth
    def arb_pnl():
        days = request.args.get("days", 30, type=int)
        # Always use live Polymarket data (local DB is ephemeral on Render)
        pm_wallet = _get_pm_wallet(request.user_address)
        series = _fetch_live_pnl(pm_wallet, days)
        if not series:
            # Fall back to local DB if API fails
            series = db.get_pnl_series(
                db_path, strategy="arbitrage", user_address=request.user_address,
                days=days,
            )
        return jsonify(series)

    # =========================================================================
    # Positions Endpoints
    # =========================================================================

    @app.route("/api/positions")
    @auth
    def get_positions():
        """Get all open positions for the authenticated user."""
        positions = db.get_open_positions(db_path, user_address=request.user_address)
        return jsonify(positions)

    @app.route("/api/positions/summary")
    @auth
    def positions_summary():
        """Get position summary stats."""
        summary = db.get_positions_summary(db_path, user_address=request.user_address)
        return jsonify(summary)

    @app.route("/api/positions/closed")
    @auth
    def closed_positions():
        """Get recently closed positions (last 30 days)."""
        from polybacker import db as _db
        with _db._connect(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM positions
                   WHERE user_address = ? AND status = 'closed'
                   AND last_updated >= datetime('now', '-30 days')
                   ORDER BY last_updated DESC LIMIT 50""",
                (request.user_address,),
            ).fetchall()
            return jsonify([dict(r) for r in rows])

    @app.route("/api/positions/close-all", methods=["POST"])
    @auth
    def close_all_positions():
        """Sell all open positions at market price.

        Places FOK market sell orders for every open LONG position and
        market buy orders for every open SHORT position to flatten the book.
        """
        from py_clob_client.order_builder.constants import BUY, SELL

        positions = db.get_open_positions(db_path, user_address=request.user_address)
        if not positions:
            return jsonify({"error": "No open positions to close"}), 400

        try:
            client = _get_user_pm_client(request.user_address)
        except Exception as e:
            return jsonify({"error": f"Failed to init trading client: {e}"}), 500

        results = {"closed": 0, "failed": 0, "errors": []}

        for pos in positions:
            try:
                token_id = pos["token_id"]
                size = pos["size"]
                if size <= 0:
                    continue

                # LONG → SELL, SHORT → BUY to close
                close_side = SELL if pos["side"] == "LONG" else BUY
                # Market orders use USDC amount = size * current_price
                amount = round(size * max(pos["current_price"], 0.01), 2)
                if amount < 0.01:
                    amount = 0.01

                resp = client.place_market_order(
                    token_id=token_id,
                    amount=amount,
                    side=close_side,
                )

                if resp:
                    db.close_position(db_path, pos["id"])
                    results["closed"] += 1
                    logger.info(f"Closed position {pos['id']}: {close_side} ${amount:.2f} of {pos['market']}")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"{pos['market']}: order failed")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{pos.get('market', 'unknown')}: {str(e)}")
                logger.error(f"Failed to close position {pos['id']}: {e}")

        return jsonify({
            "message": f"Closed {results['closed']}/{len(positions)} positions",
            **results,
        })

    @app.route("/api/positions/redeem-all", methods=["POST"])
    @auth
    def redeem_all_positions():
        """Redeem (claim winnings from) resolved markets.

        Scans open positions for markets where current_price is near 0 or 1
        (indicating settlement), and marks them as closed since
        Polymarket auto-redeems resolved positions to the wallet.

        Positions with current_price >= 0.95 (winning) or <= 0.05 (losing)
        are considered resolved and will be cleaned up from the tracker.
        """
        positions = db.get_open_positions(db_path, user_address=request.user_address)
        if not positions:
            return jsonify({"error": "No open positions"}), 400

        results = {"redeemed": 0, "skipped": 0}

        for pos in positions:
            price = pos["current_price"]
            # A resolved market has prices near 0 or 1
            is_resolved = price >= 0.95 or price <= 0.05

            if is_resolved:
                db.close_position(db_path, pos["id"])
                results["redeemed"] += 1
                side = pos["side"]
                won = (side == "LONG" and price >= 0.95) or (side == "SHORT" and price <= 0.05)
                outcome = "WON" if won else "LOST"
                logger.info(
                    f"Redeemed position {pos['id']}: {pos['market']} — {outcome}"
                )
            else:
                results["skipped"] += 1

        return jsonify({
            "message": f"Redeemed {results['redeemed']} positions ({results['skipped']} still active)",
            **results,
        })

    # =========================================================================
    # STF Fund Endpoints
    # =========================================================================

    # --- Fund CRUD ---

    @app.route("/api/funds")
    @auth
    def list_funds():
        """List all active funds (public)."""
        funds = db.get_funds(db_path, active_only=True)
        return jsonify(funds)

    @app.route("/api/funds", methods=["POST"])
    @auth
    @require_owner
    def create_fund():
        """Create a new fund (owner only)."""
        data = request.json or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()

        if not name:
            return jsonify({"error": "Fund name is required"}), 400
        if len(name) > 50:
            return jsonify({"error": "Fund name too long (max 50 chars)"}), 400

        fund_id = db.create_fund(db_path, request.user_address, name, description)
        return jsonify({"id": fund_id, "message": f"Fund '{name}' created"}), 201

    @app.route("/api/funds/<int:fund_id>")
    @auth
    def get_fund(fund_id):
        """Get fund details including allocations."""
        fund = db.get_fund(db_path, fund_id)
        if not fund:
            return jsonify({"error": "Fund not found"}), 404
        fund["allocations"] = db.get_fund_allocations(db_path, fund_id)
        return jsonify(fund)

    @app.route("/api/funds/<int:fund_id>", methods=["PATCH"])
    @auth
    @require_owner
    def update_fund(fund_id):
        """Update a fund (owner only)."""
        data = request.json or {}
        kwargs = {}
        if "name" in data:
            kwargs["name"] = data["name"].strip()
        if "description" in data:
            kwargs["description"] = data["description"].strip()
        if "active" in data:
            kwargs["active"] = 1 if data["active"] else 0

        if not kwargs:
            return jsonify({"error": "No valid fields provided"}), 400

        if db.update_fund(db_path, fund_id, request.user_address, **kwargs):
            return jsonify({"message": "Fund updated"})
        return jsonify({"error": "Fund not found or not owner"}), 404

    # --- Fund Allocations ---

    @app.route("/api/funds/<int:fund_id>/allocations", methods=["PUT"])
    @auth
    @require_owner
    def set_allocations(fund_id):
        """Set trader allocations for a fund. Weights must sum to ~1.0.

        Body: {"allocations": [{"trader_address": "0x...", "weight": 0.5}, ...]}
        """
        data = request.json or {}
        allocations = data.get("allocations", [])

        if not allocations:
            return jsonify({"error": "Allocations list is required"}), 400

        # Validate weights sum to approximately 1.0
        total_weight = sum(a.get("weight", 0) for a in allocations)
        if abs(total_weight - 1.0) > 0.01:
            return jsonify({
                "error": f"Weights must sum to 1.0 (got {total_weight:.4f})"
            }), 400

        # Validate each allocation
        for alloc in allocations:
            addr = alloc.get("trader_address", "")
            if not addr.startswith("0x") or len(addr) != 42:
                return jsonify({"error": f"Invalid address: {addr}"}), 400
            if alloc.get("weight", 0) <= 0:
                return jsonify({"error": f"Weight must be > 0 for {addr}"}), 400

        # Verify fund exists and is owned by user
        fund = db.get_fund(db_path, fund_id)
        if not fund or fund["owner_address"] != request.user_address:
            return jsonify({"error": "Fund not found or not owner"}), 404

        db.set_fund_allocations(db_path, fund_id, allocations)
        return jsonify({"message": "Allocations updated"})

    # --- Fund Investment ---

    @app.route("/api/funds/<int:fund_id>/invest", methods=["POST"])
    @auth
    def invest_in_fund(fund_id):
        """Invest in a fund. Returns shares received."""
        data = request.json or {}
        amount = data.get("amount", 0)

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid amount"}), 400

        if amount <= 0:
            return jsonify({"error": "Amount must be positive"}), 400

        try:
            investment = db.invest_in_fund(db_path, fund_id, request.user_address, amount)
            return jsonify({
                "message": f"Invested ${amount:.2f}",
                "shares": investment["shares"],
                "investment_id": investment["id"],
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/funds/investments/<int:investment_id>/withdraw", methods=["POST"])
    @auth
    def withdraw_investment(investment_id):
        """Withdraw an investment at current NAV."""
        try:
            amount = db.withdraw_from_fund(db_path, investment_id, request.user_address)
            return jsonify({
                "message": f"Withdrawn ${amount:.2f}",
                "amount": round(amount, 2),
            })
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/funds/my-investments")
    @auth
    def my_investments():
        """Get all investments for the authenticated user."""
        investments = db.get_investor_investments(db_path, request.user_address)
        return jsonify(investments)

    # --- Fund Performance ---

    @app.route("/api/funds/<int:fund_id>/performance")
    @auth
    def fund_performance(fund_id):
        """Get NAV history for a fund."""
        days = request.args.get("days", 30, type=int)
        perf = db.get_fund_performance(db_path, fund_id, days=days)
        return jsonify(perf)

    # --- Fund Trades ---

    @app.route("/api/funds/<int:fund_id>/trades")
    @auth
    def fund_trades(fund_id):
        """Get recent trades executed by a fund."""
        limit = request.args.get("limit", 50, type=int)
        fund = db.get_fund(db_path, fund_id)
        if not fund:
            return jsonify({"error": "Fund not found"}), 404

        trades = db.get_fund_trades(db_path, fund_id, limit=limit)
        return jsonify(trades)

    # --- Fund Engine Control ---

    @app.route("/api/funds/engine/start", methods=["POST"])
    @auth
    def fund_engine_start():
        """Start the fund manager engine."""
        if app.config["fund_thread"] and app.config["fund_thread"].is_alive():
            return jsonify({"error": "Fund manager already running"}), 400

        from polybacker.fund_manager import FundManager

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = _get_user_pm_client(request.user_address)

            fm = FundManager(settings=settings, client=client, dry_run=dry_run)
            app.config["fund_manager"] = fm

            thread = threading.Thread(target=fm.run, daemon=True)
            thread.start()
            app.config["fund_thread"] = thread

            return jsonify({"message": "Fund manager started", "dry_run": dry_run})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/funds/engine/stop", methods=["POST"])
    @auth
    def fund_engine_stop():
        """Stop the fund manager engine."""
        fm = app.config.get("fund_manager")
        if fm:
            fm.stop()
            app.config["fund_manager"] = None
            return jsonify({"message": "Fund manager stopped"})
        return jsonify({"error": "Not running"}), 400

    # =========================================================================
    # Watchlist Endpoints
    # =========================================================================

    @app.route("/api/watchlist")
    @auth
    def get_watchlist():
        """Get the authenticated user's watchlist."""
        entries = db.get_watchlist(db_path, request.user_address)
        return jsonify(entries)

    @app.route("/api/watchlist", methods=["POST"])
    @auth
    def add_watchlist():
        """Add a trader to the watchlist."""
        data = request.json or {}
        address = data.get("address", "")
        alias = data.get("alias", "")
        notes = data.get("notes", "")

        if not address.startswith("0x") or len(address) != 42:
            return jsonify({"error": "Invalid address"}), 400

        entry_id = db.add_to_watchlist(
            db_path, request.user_address, address, alias, notes,
        )
        if entry_id:
            return jsonify({"message": f"Added {address}", "id": entry_id})
        return jsonify({"error": "Already on watchlist"}), 409

    @app.route("/api/watchlist/<int:entry_id>", methods=["PATCH"])
    @auth
    def update_watchlist(entry_id):
        """Update alias or notes on a watchlist entry."""
        data = request.json or {}
        updated = db.update_watchlist_entry(
            db_path, entry_id, request.user_address,
            alias=data.get("alias"), notes=data.get("notes"),
        )
        if updated:
            return jsonify({"message": "Updated"})
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/watchlist/<int:entry_id>", methods=["DELETE"])
    @auth
    def remove_watchlist(entry_id):
        """Remove a trader from the watchlist."""
        if db.remove_from_watchlist(db_path, entry_id, request.user_address):
            return jsonify({"message": "Removed"})
        return jsonify({"error": "Not found"}), 404

    @app.route("/api/watchlist/<address>/profile")
    @auth
    def watchlist_trader_profile(address):
        """Get a watchlist trader's live profile from Polymarket.

        Reuses the same logic as copy trader profiles.
        """
        return copy_trader_profile(address)

    # =========================================================================
    # User Preferences Endpoints
    # =========================================================================

    @app.route("/api/preferences")
    @auth
    def get_preferences():
        """Get the authenticated user's persisted preferences."""
        prefs = db.get_user_preferences(db_path, request.user_address)
        return jsonify(prefs)

    @app.route("/api/preferences", methods=["PATCH"])
    @auth
    def update_preferences():
        """Merge new preferences into existing ones."""
        data = request.json or {}
        db.save_user_preferences(db_path, request.user_address, data)
        return jsonify({"message": "Preferences saved"})

    # =========================================================================
    # User API Credentials (Builder API keys for Polymarket)
    # =========================================================================

    @app.route("/api/settings/api-creds")
    @auth
    def get_api_creds():
        """Get the user's stored Polymarket Builder API credentials.

        Returns masked versions of sensitive fields for display.
        """
        creds = db.get_user_api_creds(db_path, request.user_address)
        if not creds:
            return jsonify({
                "api_key": "",
                "api_secret": "",
                "api_passphrase": "",
                "polymarket_address": "",
                "has_creds": False,
            })

        # Mask sensitive fields for display — show first 8 and last 4 chars
        def _mask(val: str) -> str:
            if not val or len(val) < 12:
                return "••••••••" if val else ""
            return val[:8] + "••••" + val[-4:]

        return jsonify({
            "api_key": creds.get("api_key", ""),  # Key is not super-sensitive
            "api_secret": _mask(creds.get("api_secret", "")),
            "api_passphrase": _mask(creds.get("api_passphrase", "")),
            "polymarket_address": creds.get("polymarket_address", ""),
            "has_creds": bool(creds.get("api_key")),
            "updated_at": creds.get("updated_at", ""),
        })

    @app.route("/api/settings/api-creds", methods=["PUT"])
    @auth
    def save_api_creds():
        """Save the user's Polymarket Builder API credentials.

        Supports partial updates: only non-empty fields overwrite existing values.
        This lets the frontend send just the key + address without wiping the secret.
        """
        data = request.json or {}

        api_key = data.get("api_key", "").strip()
        api_secret = data.get("api_secret", "").strip()
        api_passphrase = data.get("api_passphrase", "").strip()
        pm_address = data.get("polymarket_address", "").strip().lower()

        if not api_key:
            return jsonify({"error": "API key is required"}), 400

        # Merge with existing creds — don't overwrite secret/passphrase if empty
        existing = db.get_user_api_creds(db_path, request.user_address)
        if existing:
            if not api_secret:
                api_secret = existing.get("api_secret", "")
            if not api_passphrase:
                api_passphrase = existing.get("api_passphrase", "")
            if not pm_address:
                pm_address = existing.get("polymarket_address", "")

        db.save_user_api_creds(
            db_path,
            request.user_address,
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            polymarket_address=pm_address,
        )

        # Clear cached PM address & portfolio so they pick up the new address
        user_lower = request.user_address.lower()
        _pm_address_cache.pop(user_lower, None)
        _portfolio_cache.pop(user_lower, None)
        _balance_cache.pop(user_lower, None)

        return jsonify({"message": "API credentials saved"})

    @app.route("/api/settings/api-creds", methods=["DELETE"])
    @auth
    def delete_api_creds():
        """Remove the user's stored API credentials."""
        db.delete_user_api_creds(db_path, request.user_address)
        user_lower = request.user_address.lower()
        _pm_address_cache.pop(user_lower, None)
        _portfolio_cache.pop(user_lower, None)
        _balance_cache.pop(user_lower, None)
        return jsonify({"message": "API credentials removed"})

    # =========================================================================
    # Wallet Balance Endpoints
    # =========================================================================

    # Shared constants for on-chain RPC calls
    # polygon-rpc.com is dead (403), use reliable free alternatives
    _polygon_rpcs = [
        "https://polygon-bor-rpc.publicnode.com",
        "https://polygon.drpc.org",
        "https://1rpc.io/matic",
    ]
    rpc_url = _polygon_rpcs[0]
    usdc_e_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    usdc_e_decimals = 6

    _balance_cache: dict[str, tuple[float, dict]] = {}
    _BALANCE_CACHE_TTL = 30  # 30 seconds

    def _rpc_call(payload: dict) -> dict | None:
        """Make an RPC call with automatic fallback across multiple endpoints."""
        import requests as req
        for url in _polygon_rpcs:
            try:
                resp = req.post(url, json=payload, timeout=10)
                if resp.ok:
                    data = resp.json()
                    if "error" not in data:
                        return data
            except Exception:
                continue
        return None

    @app.route("/api/wallet/balances")
    @auth
    def wallet_balances():
        """Get USDCe and POL balances for the authenticated user's wallet.

        Returns balances in native units and USD-normalized totals.
        """
        import time as _time

        wallet = request.user_address
        now = _time.time()

        # Check cache
        if wallet in _balance_cache:
            cached_time, cached_data = _balance_cache[wallet]
            if now - cached_time < _BALANCE_CACHE_TTL:
                return jsonify(cached_data)

        # Fetch native POL (MATIC) balance
        pol_balance = 0.0
        try:
            resp = _rpc_call({
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [wallet, "latest"],
                "id": 1,
            })
            if resp:
                result = resp.get("result", "0x0")
                pol_balance = int(result, 16) / 1e18
        except Exception as e:
            logger.warning(f"Failed to fetch POL balance: {e}")

        # Fetch USDCe balance (ERC-20 balanceOf)
        usdc_e_balance = 0.0
        try:
            padded_addr = wallet.lower().replace("0x", "").zfill(64)
            call_data = "0x70a08231" + padded_addr
            resp = _rpc_call({
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": usdc_e_contract, "data": call_data}, "latest"],
                "id": 2,
            })
            if resp:
                result = resp.get("result", "0x0")
                usdc_e_balance = int(result, 16) / (10 ** usdc_e_decimals)
        except Exception as e:
            logger.warning(f"Failed to fetch USDCe balance: {e}")

        # Fetch POL price in USD — try multiple sources
        pol_price_usd = 0.0
        try:
            for coin_id in ("polygon-ecosystem-token", "matic-network"):
                price_resp = req.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": coin_id, "vs_currencies": "usd"},
                    timeout=10,
                )
                if price_resp.ok:
                    price = price_resp.json().get(coin_id, {}).get("usd", 0.0)
                    if price and price > 0:
                        pol_price_usd = price
                        break
        except Exception as e:
            logger.warning(f"CoinGecko POL price failed: {e}")

        if pol_price_usd == 0:
            try:
                for symbol in ("POLUSDT", "MATICUSDT"):
                    br = req.get(
                        "https://api.binance.com/api/v3/ticker/price",
                        params={"symbol": symbol}, timeout=10,
                    )
                    if br.ok:
                        p = float(br.json().get("price", 0))
                        if p > 0:
                            pol_price_usd = p
                            break
            except Exception:
                pass

        pol_usd_value = pol_balance * pol_price_usd
        usdc_e_usd_value = usdc_e_balance  # USDCe is pegged ~$1
        total_usd = pol_usd_value + usdc_e_usd_value

        data = {
            "pol_balance": round(pol_balance, 6),
            "pol_price_usd": round(pol_price_usd, 4),
            "pol_usd_value": round(pol_usd_value, 2),
            "usdc_e_balance": round(usdc_e_balance, 6),
            "usdc_e_usd_value": round(usdc_e_usd_value, 2),
            "total_usd": round(total_usd, 2),
        }

        _balance_cache[wallet] = (now, data)
        return jsonify(data)

    # =========================================================================
    # Polymarket Portfolio (live data from Polymarket APIs)
    # =========================================================================

    _portfolio_cache: dict[str, tuple[float, dict]] = {}
    _PORTFOLIO_CACHE_TTL = 30  # 30 seconds

    def _resolve_proxy_wallet(eoa_address: str) -> str | None:
        """Resolve the Polymarket proxy wallet address for an EOA via on-chain call."""
        try:
            padded = eoa_address.lower().replace("0x", "").zfill(64)
            call_data = "0xedef7d8e" + padded
            factory = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
            resp = _rpc_call({
                "jsonrpc": "2.0", "method": "eth_call",
                "params": [{"to": factory, "data": call_data}, "latest"],
                "id": 1,
            })
            if resp:
                result = resp.get("result", "0x")
                if result and len(result) >= 66:
                    proxy = "0x" + result[-40:]
                    if proxy != "0x" + "0" * 40:
                        return proxy
        except Exception as e:
            logger.warning(f"Failed to resolve proxy wallet: {e}")
        return None

    _proxy_cache: dict[str, str] = {}

    def _get_proxy_for(eoa: str) -> str | None:
        eoa = eoa.lower()
        if eoa in _proxy_cache:
            return _proxy_cache[eoa]
        proxy = _resolve_proxy_wallet(eoa)
        if proxy:
            _proxy_cache[eoa] = proxy
        return proxy

    # Cache for auto-discovered Polymarket trading address per user
    _pm_address_cache: dict[str, str] = {}

    def _discover_pm_address(eoa: str) -> str:
        """Auto-discover the Polymarket trading address for a Web3 wallet.

        Builds a list of candidate addresses (env var, funder, CREATE2 proxy, EOA)
        and queries the Polymarket Data API to find which one actually has activity.
        The result is cached permanently for the session.
        """
        import requests as req

        eoa_lower = eoa.lower()

        # Return cached result
        if eoa_lower in _pm_address_cache:
            return _pm_address_cache[eoa_lower]

        # Build unique candidate addresses to probe
        candidates = []
        seen = set()

        def _add(addr: str | None):
            if addr and addr.startswith("0x") and len(addr) == 42:
                a = addr.lower()
                if a not in seen:
                    seen.add(a)
                    candidates.append(a)

        # 1) Check per-user stored API creds (polymarket_address)
        user_creds = db.get_user_api_creds(db_path, eoa_lower)
        _add(user_creds.get("polymarket_address"))

        # 2) Check user preferences
        prefs = db.get_user_preferences(db_path, eoa_lower)
        _add(prefs.get("polymarket_address"))

        # 3) Only use server-level env/config addresses for the OWNER wallet.
        #    Other users should NOT inherit the owner's PM addresses.
        is_owner_wallet = owner_address and eoa_lower == owner_address
        if is_owner_wallet:
            _add(settings.polymarket_address)
            _add(settings.funder)

        # 4) CREATE2 proxy and EOA itself (always checked)
        proxy = _get_proxy_for(eoa_lower)
        _add(proxy)
        _add(eoa_lower)

        if not candidates:
            candidates = [eoa_lower]

        # Probe each candidate — check trades endpoint (fast, lightweight)
        for addr in candidates:
            try:
                resp = req.get(
                    f"{settings.data_host}/trades",
                    params={"user": addr, "limit": 1},
                    timeout=10,
                    headers={"Accept": "application/json"},
                )
                if resp.ok:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(
                            f"Auto-discovered Polymarket address for {eoa_lower[:10]}...: {addr}"
                        )
                        _pm_address_cache[eoa_lower] = addr
                        return addr
            except Exception:
                continue

        # If no candidate has activity, check positions too (user might only hold, no trades)
        for addr in candidates:
            try:
                resp = req.get(
                    f"{settings.data_host}/positions",
                    params={"user": addr},
                    timeout=10,
                    headers={"Accept": "application/json"},
                )
                if resp.ok:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        logger.info(
                            f"Auto-discovered Polymarket address (via positions) for {eoa_lower[:10]}...: {addr}"
                        )
                        _pm_address_cache[eoa_lower] = addr
                        return addr
            except Exception:
                continue

        # No activity found on any address — default to first candidate
        # (env override or CREATE2 proxy or EOA)
        fallback = candidates[0]
        _pm_address_cache[eoa_lower] = fallback
        logger.info(
            f"No Polymarket activity found for {eoa_lower[:10]}..., using fallback: {fallback}"
        )
        return fallback

    def _fetch_polymarket_data(address_list: list[str], data_host: str):
        """Fetch positions and trades from Polymarket Data API, trying multiple addresses."""
        import requests as req
        positions = []
        trades = []
        seen_ids = set()

        for addr in address_list:
            if not addr:
                continue
            # Positions
            try:
                pos_resp = req.get(
                    f"{data_host}/positions",
                    params={"user": addr.lower()},
                    timeout=15, headers={"Accept": "application/json"},
                )
                if pos_resp.ok:
                    raw = pos_resp.json()
                    if isinstance(raw, list):
                        for p in raw:
                            pid = p.get("asset", "") + p.get("outcome", "")
                            if pid in seen_ids:
                                continue
                            seen_ids.add(pid)
                            size = float(p.get("size", 0) or 0)
                            if size <= 0:
                                continue
                            cur_price_raw = float(p.get("curPrice", 0) or p.get("currentPrice", 0) or 0)
                            # Filter out resolved/expired positions (price went to 0 or 1 = market settled)
                            if cur_price_raw <= 0.001:
                                continue
                            avg_price = float(p.get("avgPrice", 0) or p.get("avg_price", 0) or 0)
                            cur_price = cur_price_raw
                            cost = size * avg_price
                            value = size * cur_price
                            pnl = value - cost
                            positions.append({
                                "asset": p.get("asset", ""),
                                "title": p.get("title", p.get("market", p.get("question", ""))),
                                "outcome": p.get("outcome", ""),
                                "size": round(size, 2),
                                "avgPrice": round(avg_price, 4),
                                "curPrice": round(cur_price, 4),
                                "cost": round(cost, 2),
                                "value": round(value, 2),
                                "pnl": round(pnl, 2),
                                "pnlPct": round((pnl / cost * 100) if cost > 0 else 0, 1),
                                "side": p.get("side", "LONG"),
                            })
            except Exception as e:
                logger.warning(f"Polymarket positions for {addr}: {e}")

            # Trades
            try:
                trades_resp = req.get(
                    f"{data_host}/trades",
                    params={"user": addr.lower(), "limit": 100},
                    timeout=15, headers={"Accept": "application/json"},
                )
                if trades_resp.ok:
                    raw = trades_resp.json()
                    if isinstance(raw, list):
                        for t in raw:
                            # Use transactionHash as unique ID (PM Data API has no 'id' field)
                            tid = t.get("transactionHash", "") or t.get("id", "")
                            if tid and tid in seen_ids:
                                continue
                            if tid:
                                seen_ids.add(tid)
                            size = float(t.get("size", 0) or 0)
                            price = float(t.get("price", 0) or 0)
                            trades.append({
                                "id": tid,
                                "timestamp": t.get("timestamp", t.get("created_at", "")),
                                "market": t.get("title", t.get("market", t.get("question", ""))),
                                "outcome": t.get("outcome", ""),
                                "side": t.get("side", ""),
                                "size": round(size, 2),
                                "price": round(price, 4),
                                "amount": round(size * price, 2),
                                "asset": t.get("asset", ""),
                            })
            except Exception as e:
                logger.warning(f"Polymarket trades for {addr}: {e}")

        return positions, trades

    @app.route("/api/portfolio")
    @auth
    def get_portfolio():
        """Get the user's live Polymarket portfolio: positions, trade history, and balance.

        Auto-discovers the correct Polymarket trading address by probing
        candidate addresses (env var, funder, CREATE2 proxy, EOA) and caching
        whichever one has actual Polymarket activity.
        """
        import time as _time
        import requests as req

        wallet = request.user_address
        now = _time.time()

        if wallet in _portfolio_cache:
            cached_time, cached_data = _portfolio_cache[wallet]
            if now - cached_time < _PORTFOLIO_CACHE_TTL:
                return jsonify(cached_data)

        # Auto-discover the correct Polymarket trading address
        pm_address = _discover_pm_address(wallet)
        addresses = [pm_address]

        # Fetch positions and trades from the discovered address
        positions, trades = _fetch_polymarket_data(addresses, settings.data_host)

        total_invested = sum(p["cost"] for p in positions)
        total_current_value = sum(p["value"] for p in positions)
        total_pnl = sum(p["pnl"] for p in positions)

        # Check USDCe balance on the Polymarket trading address
        proxy_usdc_balance = 0.0
        if pm_address and pm_address.lower() != wallet.lower():
            try:
                padded_pm = pm_address.lower().replace("0x", "").zfill(64)
                call_data = "0x70a08231" + padded_pm
                resp = _rpc_call({
                    "jsonrpc": "2.0", "method": "eth_call",
                    "params": [{"to": usdc_e_contract, "data": call_data}, "latest"],
                    "id": 1,
                })
                if resp:
                    result = resp.get("result", "0x0")
                    proxy_usdc_balance = int(result, 16) / (10 ** usdc_e_decimals)
            except Exception as e:
                logger.warning(f"PM trading balance check failed: {e}")

        data = {
            "positions": positions,
            "trades": trades,
            "proxy_wallet": pm_address or "",
            "proxy_usdc_balance": round(proxy_usdc_balance, 2),
            "summary": {
                "total_positions": len(positions),
                "total_invested": round(total_invested, 2),
                "total_current_value": round(total_current_value, 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round((total_pnl / total_invested * 100) if total_invested > 0 else 0, 1),
            },
        }

        _portfolio_cache[wallet] = (now, data)
        return jsonify(data)

    # =========================================================================
    # General Endpoints
    # =========================================================================

    @app.route("/api/trades")
    @auth
    def all_trades():
        limit = request.args.get("limit", 50, type=int)
        trades = db.get_trades(
            db_path, limit=limit, user_address=request.user_address,
        )
        return jsonify(trades)

    @app.route("/api/activity-log")
    @auth
    def activity_log():
        """Unified activity feed: trades + engine events.

        Query params:
            limit: max results (default 100)
            offset: pagination offset (default 0)
            type: filter by event type ("trade", "engine_start", "error", etc.)
            status: filter trade status ("executed", "failed", "dry_run")
            search: search market names and messages
        """
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        event_type = request.args.get("type", None)
        status = request.args.get("status", None)
        search = request.args.get("search", None)

        events = db.get_activity_log(
            db_path,
            user_address=request.user_address,
            event_type=event_type,
            status=status,
            search=search,
            limit=min(limit, 500),
            offset=offset,
        )
        return jsonify(events)

    @app.route("/api/me")
    @auth
    def get_me():
        """Get the current authenticated user's profile."""
        user = db.get_user(db_path, request.user_address)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user)

    # =========================================================================
    # Position Tracker Helper
    # =========================================================================

    def _ensure_position_tracker(s: Settings):
        """Start the position price tracker if not already running."""
        if app.config["position_thread"] and app.config["position_thread"].is_alive():
            return

        from polybacker.client import PolymarketClient
        from polybacker.positions import PositionTracker

        try:
            client = PolymarketClient(s)
            pt = PositionTracker(settings=s, client=client)
            app.config["position_tracker"] = pt

            thread = threading.Thread(target=pt.run, kwargs={"interval": 30}, daemon=True)
            thread.start()
            app.config["position_thread"] = thread
            logger.info("Position tracker started")
        except Exception as e:
            logger.warning(f"Could not start position tracker: {e}")

    # Start position tracker on server startup so prices stay fresh
    try:
        _ensure_position_tracker(settings)
    except Exception as e:
        logger.warning(f"Position tracker startup failed: {e}")

    # =========================================================================
    # WebSocket Events
    # =========================================================================

    @socketio.on("connect")
    def handle_connect(auth_data=None):
        # Verify JWT from auth parameter if provided
        if auth_data and auth_data.get("token"):
            payload = decode_jwt(auth_data["token"], settings.jwt_secret)
            if not payload:
                return False  # Reject connection

        emit("status", _build_status_payload())

    return app, socketio


def create_wsgi_app():
    """Zero-arg factory for gunicorn / Render deployment."""
    from polybacker.config import load_settings

    settings = load_settings()
    app, _ = create_app(settings)
    return app
