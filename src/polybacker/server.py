"""Flask API server for the Polybacker dashboard.

Provides REST endpoints and WebSocket events for real-time monitoring
of copy trading and arbitrage bots. Supports SIWE authentication for
multi-user access.
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
        logger.info(f"Owner address: {owner_address}")

    app.config["settings"] = settings
    app.config["owner_address"] = owner_address
    app.config["copy_trader"] = None
    app.config["arb_scanner"] = None
    app.config["copy_thread"] = None
    app.config["arb_thread"] = None

    # Create auth decorator bound to this app's JWT secret
    auth = require_auth(settings.jwt_secret)

    # =========================================================================
    # Dashboard (legacy HTML — Next.js frontend is the primary UI)
    # =========================================================================

    @app.route("/")
    def index():
        return send_from_directory(str(static_dir), "dashboard.html")

    # =========================================================================
    # Auth Endpoints
    # =========================================================================

    @app.route("/api/auth/nonce", methods=["POST"])
    def auth_nonce():
        """Generate a nonce for SIWE authentication."""
        nonce = db.create_session_nonce(db_path)
        return jsonify({"nonce": nonce})

    @app.route("/api/auth/verify", methods=["POST"])
    def auth_verify():
        """Verify a SIWE message signature and issue a JWT token."""
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
        if owner_address and address == owner_address:
            role = "owner"

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
        return jsonify({
            "copy_trading": "running" if copy_running else "stopped",
            "arbitrage": "running" if arb_running else "stopped",
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
        return jsonify(stats)

    @app.route("/api/copy/pnl")
    @auth
    def copy_pnl():
        days = request.args.get("days", 30, type=int)
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
        return jsonify(series)

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
        emit("status", {
            "copy_trading": "running" if copy_running else "stopped",
            "arbitrage": "running" if arb_running else "stopped",
        })

    return app, socketio


def create_wsgi_app():
    """Zero-arg factory for gunicorn / Render deployment."""
    from polybacker.config import load_settings

    settings = load_settings()
    app, _ = create_app(settings)
    return app
