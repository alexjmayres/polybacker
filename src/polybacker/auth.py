"""Authentication via Sign-In with Ethereum (SIWE) and JWT tokens."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Optional

import jwt
from flask import request, jsonify
from siwe import SiweMessage


def generate_nonce() -> str:
    """Generate a random nonce for SIWE authentication."""
    return secrets.token_hex(16)


def verify_siwe_message(message_str: str, signature: str) -> str:
    """Verify a SIWE message signature.

    Args:
        message_str: The EIP-4361 formatted SIWE message string.
        signature: The hex signature from the wallet.

    Returns:
        The recovered Ethereum address (lowercased).

    Raises:
        Exception: If verification fails.
    """
    message = SiweMessage.from_message(message_str)
    message.verify(signature)
    return message.address.lower()


def create_jwt(
    address: str,
    role: str,
    secret: str,
    expiry_hours: int = 72,
) -> tuple[str, datetime]:
    """Create a JWT token for an authenticated user.

    Returns:
        Tuple of (token_string, expiry_datetime).
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=expiry_hours)
    payload = {
        "sub": address.lower(),
        "role": role,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, expires_at


def decode_jwt(token: str, secret: str) -> Optional[dict]:
    """Decode and verify a JWT token.

    Returns:
        The decoded payload dict, or None if invalid/expired.
    """
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def require_auth(secret: str):
    """Create a decorator that requires a valid JWT Bearer token.

    Usage:
        @require_auth(settings.jwt_secret)
        def my_endpoint():
            # request.user_address and request.user_role are set
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid token"}), 401

            token = auth_header[7:]
            payload = decode_jwt(token, secret)
            if not payload:
                return jsonify({"error": "Invalid or expired token"}), 401

            # Attach user info to the request
            request.user_address = payload["sub"]
            request.user_role = payload.get("role", "user")
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_owner(f):
    """Decorator that checks the authenticated user has the 'owner' role.

    Must be used AFTER @require_auth so request.user_role is set.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if getattr(request, "user_role", None) != "owner":
            return jsonify({"error": "Owner access required"}), 403
        return f(*args, **kwargs)
    return decorated
