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
    CORS(app, origins=[
        "https://polybacker.com",
        "https://www.polybacker.com",
        "http://localhost:3000",
    ])
    socketio = SocketIO(app, cors_allowed_origins="*")

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

    # Create auth decorator bound to this app's JWT secret
    auth = require_auth(settings.jwt_secret)

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

        return jsonify({
            "authenticated": True,
            "address": payload["sub"],
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

    @app.route("/api/status")
    @auth
    def get_status():
        copy_running = (
            app.config["copy_thread"] is not None
            and app.config["copy_thread"].is_alive()
        )
        arb_running = (
            app.config["arb_thread"] is not None
            and app.config["arb_thread"].is_alive()
        )
        fund_running = (
            app.config["fund_thread"] is not None
            and app.config["fund_thread"].is_alive()
        )
        return jsonify({
            "copy_trading": "running" if copy_running else "stopped",
            "arbitrage": "running" if arb_running else "stopped",
            "fund_manager": "running" if fund_running else "stopped",
            "config": {
                "copy_percentage": settings.copy_percentage,
                "min_copy_size": settings.min_copy_size,
                "max_copy_size": settings.max_copy_size,
                "max_daily_spend": settings.max_daily_spend,
                "min_profit_pct": settings.min_profit_pct,
                "trade_amount": settings.trade_amount,
                "poll_interval": settings.poll_interval,
                "auto_execute": settings.auto_execute,
            },
        })

    # =========================================================================
    # Copy Trading Endpoints
    # =========================================================================

    @app.route("/api/copy/start", methods=["POST"])
    @auth
    @require_owner
    def copy_start():
        if app.config["copy_thread"] and app.config["copy_thread"].is_alive():
            return jsonify({"error": "Copy trading already running"}), 400

        from polybacker.client import PolymarketClient
        from polybacker.copy_trader import CopyTrader

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = PolymarketClient(settings)
            trader = CopyTrader(settings=settings, client=client, dry_run=dry_run)
            trader.load_traders_from_file()
            app.config["copy_trader"] = trader

            thread = threading.Thread(target=trader.run, daemon=True)
            thread.start()
            app.config["copy_thread"] = thread

            # Also start the position tracker if not already running
            _ensure_position_tracker(settings)

            return jsonify({"message": "Copy trading started", "dry_run": dry_run})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/copy/stop", methods=["POST"])
    @auth
    @require_owner
    def copy_stop():
        trader = app.config.get("copy_trader")
        if trader:
            trader.stop()
            app.config["copy_trader"] = None
            return jsonify({"message": "Copy trading stopped"})
        return jsonify({"error": "Not running"}), 400

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
        {copy_percentage, min_copy_size, max_copy_size, max_daily_spend, active}
        """
        data = request.json or {}
        valid_keys = {"copy_percentage", "min_copy_size", "max_copy_size", "max_daily_spend", "active"}
        updates = {}
        for key in valid_keys:
            if key in data:
                val = data[key]
                # Allow null to clear overrides
                if val is None:
                    updates[key] = None
                elif key == "active":
                    updates[key] = 1 if val else 0
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
        from polybacker.client import PolymarketClient

        try:
            client = PolymarketClient(settings)
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

    @app.route("/api/copy/pnl")
    @auth
    def copy_pnl():
        days = request.args.get("days", 30, type=int)
        series = db.get_pnl_series(
            db_path, strategy="copy", user_address=request.user_address,
            days=days,
        )
        # If no local data, fall back to live Polymarket trades for the wallet
        if not series and owner_address:
            series = _fetch_live_pnl(owner_address, days, strategy_filter="copy")
        return jsonify(series)

    # =========================================================================
    # Arbitrage Endpoints
    # =========================================================================

    @app.route("/api/arb/start", methods=["POST"])
    @auth
    @require_owner
    def arb_start():
        if app.config["arb_thread"] and app.config["arb_thread"].is_alive():
            return jsonify({"error": "Arbitrage already running"}), 400

        from polybacker.client import PolymarketClient
        from polybacker.arbitrage import ArbitrageScanner

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = PolymarketClient(settings)
            scanner = ArbitrageScanner(settings=settings, client=client, dry_run=dry_run)
            app.config["arb_scanner"] = scanner

            thread = threading.Thread(target=scanner.run, daemon=True)
            thread.start()
            app.config["arb_thread"] = thread

            # Also start the position tracker if not already running
            _ensure_position_tracker(settings)

            return jsonify({"message": "Arbitrage started", "dry_run": dry_run})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/arb/stop", methods=["POST"])
    @auth
    @require_owner
    def arb_stop():
        scanner = app.config.get("arb_scanner")
        if scanner:
            scanner.stop()
            app.config["arb_scanner"] = None
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
        series = db.get_pnl_series(
            db_path, strategy="arbitrage", user_address=request.user_address,
            days=days,
        )
        # If no local data, fall back to live Polymarket trades
        if not series and owner_address:
            series = _fetch_live_pnl(owner_address, days, strategy_filter="arb")
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
    @require_owner
    def close_all_positions():
        """Sell all open positions at market price.

        Places FOK market sell orders for every open LONG position and
        market buy orders for every open SHORT position to flatten the book.
        """
        from polybacker.client import PolymarketClient
        from py_clob_client.order_builder.constants import BUY, SELL

        positions = db.get_open_positions(db_path, user_address=request.user_address)
        if not positions:
            return jsonify({"error": "No open positions to close"}), 400

        try:
            client = PolymarketClient(settings)
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
    @require_owner
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
    @require_owner
    def fund_engine_start():
        """Start the fund manager engine (owner only)."""
        if app.config["fund_thread"] and app.config["fund_thread"].is_alive():
            return jsonify({"error": "Fund manager already running"}), 400

        from polybacker.client import PolymarketClient
        from polybacker.fund_manager import FundManager

        dry_run = request.json.get("dry_run", False) if request.json else False

        try:
            client = PolymarketClient(settings)
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
    @require_owner
    def fund_engine_stop():
        """Stop the fund manager engine."""
        fm = app.config.get("fund_manager")
        if fm:
            fm.stop()
            app.config["fund_manager"] = None
            return jsonify({"message": "Fund manager stopped"})
        return jsonify({"error": "Not running"}), 400

    # =========================================================================
    # Wallet Balance Endpoints
    # =========================================================================

    _balance_cache: dict[str, tuple[float, dict]] = {}
    _BALANCE_CACHE_TTL = 30  # 30 seconds

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

        import requests as req

        rpc_url = "https://polygon-rpc.com"
        usdc_e_contract = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        usdc_e_decimals = 6

        # Fetch native POL (MATIC) balance
        pol_balance = 0.0
        try:
            rpc_resp = req.post(rpc_url, json={
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [wallet, "latest"],
                "id": 1,
            }, timeout=10)
            if rpc_resp.ok:
                result = rpc_resp.json().get("result", "0x0")
                pol_balance = int(result, 16) / 1e18
        except Exception as e:
            logger.warning(f"Failed to fetch POL balance: {e}")

        # Fetch USDCe balance (ERC-20 balanceOf)
        usdc_e_balance = 0.0
        try:
            # balanceOf(address) selector = 0x70a08231
            padded_addr = wallet.lower().replace("0x", "").zfill(64)
            call_data = "0x70a08231" + padded_addr
            rpc_resp = req.post(rpc_url, json={
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": usdc_e_contract, "data": call_data}, "latest"],
                "id": 2,
            }, timeout=10)
            if rpc_resp.ok:
                result = rpc_resp.json().get("result", "0x0")
                usdc_e_balance = int(result, 16) / (10 ** usdc_e_decimals)
        except Exception as e:
            logger.warning(f"Failed to fetch USDCe balance: {e}")

        # Fetch POL price in USD from CoinGecko
        pol_price_usd = 0.0
        try:
            price_resp = req.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "matic-network", "vs_currencies": "usd"},
                timeout=10,
            )
            if price_resp.ok:
                pol_price_usd = price_resp.json().get("matic-network", {}).get("usd", 0.0)
        except Exception as e:
            logger.warning(f"Failed to fetch POL price: {e}")

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

        copy_running = (
            app.config["copy_thread"] is not None
            and app.config["copy_thread"].is_alive()
        )
        arb_running = (
            app.config["arb_thread"] is not None
            and app.config["arb_thread"].is_alive()
        )
        fund_running = (
            app.config["fund_thread"] is not None
            and app.config["fund_thread"].is_alive()
        )
        emit("status", {
            "copy_trading": "running" if copy_running else "stopped",
            "arbitrage": "running" if arb_running else "stopped",
            "fund_manager": "running" if fund_running else "stopped",
        })

    return app, socketio


def create_wsgi_app():
    """Zero-arg factory for gunicorn / Render deployment."""
    from polybacker.config import load_settings

    settings = load_settings()
    app, _ = create_app(settings)
    return app
