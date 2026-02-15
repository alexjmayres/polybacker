"""SQLite database for trade history, followed traders, and dedup tracking."""

from __future__ import annotations

import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional


def init_db(db_path: str = "polybacker.db") -> str:
    """Create database tables if they don't exist. Returns the db_path."""
    with _connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                strategy TEXT NOT NULL,           -- 'copy' or 'arbitrage'
                market TEXT,                       -- market question / name
                token_id TEXT NOT NULL,
                side TEXT NOT NULL,                 -- 'BUY' or 'SELL'
                amount REAL NOT NULL,               -- USDC amount
                price REAL,                         -- execution price
                expected_profit REAL,
                copied_from TEXT,                   -- trader address (copy trades only)
                original_trade_id TEXT,             -- source trade ID (copy trades only)
                status TEXT NOT NULL DEFAULT 'executed',  -- 'executed', 'failed', 'dry_run'
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS followed_traders (
                address TEXT NOT NULL,
                alias TEXT,
                added_at TEXT NOT NULL DEFAULT (datetime('now')),
                active INTEGER NOT NULL DEFAULT 1,
                total_copied INTEGER NOT NULL DEFAULT 0,
                total_spent REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS seen_trade_ids (
                trade_id TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Auth tables
            CREATE TABLE IF NOT EXISTS users (
                address TEXT PRIMARY KEY,
                role TEXT NOT NULL DEFAULT 'user',
                display_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                nonce TEXT NOT NULL,
                token TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT,
                verified INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
            CREATE INDEX IF NOT EXISTS idx_trades_copied_from ON trades(copied_from);
            CREATE INDEX IF NOT EXISTS idx_seen_trade_ids_first_seen ON seen_trade_ids(first_seen);
            CREATE INDEX IF NOT EXISTS idx_sessions_nonce ON sessions(nonce);
        """)

        # Run migrations for multi-user support
        _migrate_db(conn)

    return db_path


def _migrate_db(conn):
    """Run schema migrations for multi-user support."""
    # Add user_address to followed_traders if missing
    cursor = conn.execute("PRAGMA table_info(followed_traders)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_address" not in columns:
        conn.execute(
            "ALTER TABLE followed_traders ADD COLUMN user_address TEXT DEFAULT 'legacy'"
        )

    # Make followed_traders primary key include user_address
    # (can't alter PK in SQLite, so we work with composite uniqueness via queries)

    # Add user_address to trades if missing
    cursor = conn.execute("PRAGMA table_info(trades)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_address" not in columns:
        conn.execute(
            "ALTER TABLE trades ADD COLUMN user_address TEXT DEFAULT 'legacy'"
        )

    # Add indexes for user scoping
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_followed_traders_user ON followed_traders(user_address)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_trades_user ON trades(user_address)"
    )


@contextmanager
def _connect(db_path: str):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- User Operations ---

def create_or_get_user(
    db_path: str,
    address: str,
    role: str = "user",
) -> dict:
    """Create a user if they don't exist, or return existing user."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE address = ?", (address,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET last_login = datetime('now') WHERE address = ?",
                (address,),
            )
            return dict(existing)

        conn.execute(
            "INSERT INTO users (address, role) VALUES (?, ?)",
            (address, role),
        )
        row = conn.execute(
            "SELECT * FROM users WHERE address = ?", (address,)
        ).fetchone()
        return dict(row)


def get_user(db_path: str, address: str) -> Optional[dict]:
    """Get a user by address."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE address = ?", (address,)
        ).fetchone()
        return dict(row) if row else None


def create_session_nonce(db_path: str) -> str:
    """Generate and store a nonce for SIWE authentication."""
    nonce = secrets.token_hex(16)
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (nonce) VALUES (?)",
            (nonce,),
        )
    return nonce


def verify_session_nonce(db_path: str, nonce: str) -> bool:
    """Check if a nonce exists and hasn't been used yet."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE nonce = ? AND verified = 0",
            (nonce,),
        ).fetchone()
        return row is not None


def mark_session_verified(
    db_path: str,
    nonce: str,
    address: str,
    token: str,
    expires_at: str,
):
    """Mark a session nonce as verified and store the JWT token."""
    with _connect(db_path) as conn:
        conn.execute(
            """UPDATE sessions
               SET address = ?, token = ?, expires_at = ?, verified = 1
               WHERE nonce = ? AND verified = 0""",
            (address.lower(), token, expires_at, nonce),
        )


def cleanup_expired_sessions(db_path: str) -> int:
    """Remove expired sessions. Returns count deleted."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE expires_at < datetime('now') OR "
            "(verified = 0 AND created_at < datetime('now', '-1 hour'))"
        )
        return cursor.rowcount


def claim_legacy_data(db_path: str, owner_address: str):
    """Claim all 'legacy' data for the owner address."""
    owner_address = owner_address.lower().strip()
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE followed_traders SET user_address = ? WHERE user_address = 'legacy'",
            (owner_address,),
        )
        conn.execute(
            "UPDATE trades SET user_address = ? WHERE user_address = 'legacy'",
            (owner_address,),
        )


# --- Trade Operations ---

def record_trade(
    db_path: str,
    strategy: str,
    token_id: str,
    side: str,
    amount: float,
    market: str = "",
    price: float = 0.0,
    expected_profit: float = 0.0,
    copied_from: str = "",
    original_trade_id: str = "",
    status: str = "executed",
    notes: str = "",
    user_address: Optional[str] = None,
) -> int:
    """Record a trade. Returns the trade ID."""
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO trades
               (strategy, market, token_id, side, amount, price, expected_profit,
                copied_from, original_trade_id, status, notes, user_address)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (strategy, market, token_id, side, amount, price, expected_profit,
             copied_from, original_trade_id, status, notes, user_address),
        )
        return cursor.lastrowid


def get_trades(
    db_path: str,
    strategy: Optional[str] = None,
    limit: int = 50,
    user_address: Optional[str] = None,
) -> list[dict]:
    """Get recent trades, optionally filtered by strategy and user."""
    with _connect(db_path) as conn:
        conditions = []
        params = []

        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM trades {where} ORDER BY timestamp DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_daily_spend(
    db_path: str,
    strategy: str = "copy",
    user_address: Optional[str] = None,
) -> float:
    """Get total USDC spent today for a given strategy."""
    today = date.today().isoformat()
    with _connect(db_path) as conn:
        conditions = ["strategy = ?", "status = 'executed'", "date(timestamp) = ?"]
        params: list = [strategy, today]

        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        where = " AND ".join(conditions)
        row = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM trades WHERE {where}",
            params,
        ).fetchone()
        return row["total"]


def get_pnl_series(
    db_path: str,
    strategy: Optional[str] = None,
    user_address: Optional[str] = None,
    days: int = 30,
) -> list[dict]:
    """Get daily PnL series for charting.

    Returns a list of {date, trades, spent, profit, cumulative_profit} dicts.
    For copy trades, profit = expected_profit. For arb trades, profit = expected_profit.
    """
    with _connect(db_path) as conn:
        conditions = ["status IN ('executed', 'dry_run')"]
        params: list = []

        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        conditions.append(f"date(timestamp) >= date('now', '-{int(days)} days')")
        where = " AND ".join(conditions)

        rows = conn.execute(
            f"""SELECT
                date(timestamp) as date,
                COUNT(*) as trades,
                COALESCE(SUM(amount), 0) as spent,
                COALESCE(SUM(expected_profit), 0) as profit
            FROM trades
            WHERE {where}
            GROUP BY date(timestamp)
            ORDER BY date(timestamp) ASC""",
            params,
        ).fetchall()

        series = []
        cumulative = 0.0
        for row in rows:
            cumulative += row["profit"]
            series.append({
                "date": row["date"],
                "trades": row["trades"],
                "spent": round(row["spent"], 2),
                "profit": round(row["profit"], 2),
                "cumulative_profit": round(cumulative, 2),
            })
        return series


# --- Trader Operations ---

def add_trader(
    db_path: str,
    address: str,
    alias: str = "",
    user_address: Optional[str] = None,
) -> bool:
    """Add a trader to follow. Returns True if added, False if already exists."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        # Check for existing active follow by this user
        existing = conn.execute(
            "SELECT 1 FROM followed_traders WHERE address = ? AND user_address = ? AND active = 1",
            (address, user_address),
        ).fetchone()
        if existing:
            return False

        # Check for deactivated follow — reactivate
        reactivated = conn.execute(
            "UPDATE followed_traders SET active = 1, alias = ? WHERE address = ? AND user_address = ? AND active = 0",
            (alias, address, user_address),
        )
        if reactivated.rowcount > 0:
            return True

        conn.execute(
            "INSERT INTO followed_traders (address, alias, user_address) VALUES (?, ?, ?)",
            (address, alias, user_address),
        )
        return True


def remove_trader(
    db_path: str,
    address: str,
    user_address: Optional[str] = None,
) -> bool:
    """Remove a trader (sets inactive). Returns True if found."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        conditions = ["address = ?"]
        params = [address]
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        cursor = conn.execute(
            f"UPDATE followed_traders SET active = 0 WHERE {' AND '.join(conditions)}",
            params,
        )
        return cursor.rowcount > 0


def get_active_traders(
    db_path: str,
    user_address: Optional[str] = None,
) -> list[dict]:
    """Get all active followed traders, optionally scoped to a user."""
    with _connect(db_path) as conn:
        if user_address:
            rows = conn.execute(
                "SELECT * FROM followed_traders WHERE active = 1 AND user_address = ? ORDER BY added_at",
                (user_address,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM followed_traders WHERE active = 1 ORDER BY added_at",
            ).fetchall()
        return [dict(r) for r in rows]


def update_trader_stats(
    db_path: str,
    address: str,
    amount_spent: float,
    user_address: Optional[str] = None,
):
    """Increment a trader's copy count and total spent."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        conditions = ["address = ?"]
        params: list = [amount_spent, address]
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        conn.execute(
            f"""UPDATE followed_traders
               SET total_copied = total_copied + 1, total_spent = total_spent + ?
               WHERE {' AND '.join(conditions)}""",
            params,
        )


# --- Dedup Operations ---

def is_trade_seen(db_path: str, trade_id: str) -> bool:
    """Check if we've already processed this trade."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_trade_ids WHERE trade_id = ?",
            (trade_id,),
        ).fetchone()
        return row is not None


def mark_trade_seen(db_path: str, trade_id: str):
    """Mark a trade ID as seen."""
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_trade_ids (trade_id) VALUES (?)",
            (trade_id,),
        )


def cleanup_old_seen_trades(db_path: str, days: int = 7):
    """Remove seen_trade_ids older than N days to prevent table bloat."""
    with _connect(db_path) as conn:
        conn.execute(
            "DELETE FROM seen_trade_ids WHERE first_seen < datetime('now', ?)",
            (f"-{days} days",),
        )


# --- Stats ---

def get_copy_stats(
    db_path: str,
    user_address: Optional[str] = None,
) -> dict:
    """Get summary statistics for copy trading."""
    with _connect(db_path) as conn:
        conditions = ["strategy = 'copy'"]
        params = []
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        where = " AND ".join(conditions)
        row = conn.execute(
            f"""SELECT
                COUNT(*) as total_trades,
                COALESCE(SUM(amount), 0) as total_spent,
                COALESCE(SUM(CASE WHEN status = 'executed' THEN amount ELSE 0 END), 0) as total_executed,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) as failed_trades,
                COUNT(DISTINCT copied_from) as unique_traders_copied
               FROM trades WHERE {where}""",
            params,
        ).fetchone()
        return dict(row)


def get_arb_stats(
    db_path: str,
    user_address: Optional[str] = None,
) -> dict:
    """Get summary statistics for arbitrage trading."""
    with _connect(db_path) as conn:
        conditions = ["strategy = 'arbitrage'"]
        params = []
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)

        where = " AND ".join(conditions)
        row = conn.execute(
            f"""SELECT
                COUNT(*) as total_trades,
                COALESCE(SUM(amount), 0) as total_spent,
                COALESCE(SUM(expected_profit), 0) as total_expected_profit,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) as failed_trades
               FROM trades WHERE {where}""",
            params,
        ).fetchone()
        return dict(row)
