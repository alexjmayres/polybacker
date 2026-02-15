"""SQLite database for trade history, followed traders, positions, funds, and dedup tracking."""

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
                strategy TEXT NOT NULL,
                market TEXT,
                token_id TEXT NOT NULL,
                side TEXT NOT NULL,
                amount REAL NOT NULL,
                price REAL,
                expected_profit REAL,
                copied_from TEXT,
                original_trade_id TEXT,
                status TEXT NOT NULL DEFAULT 'executed',
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

            -- Whitelist table
            CREATE TABLE IF NOT EXISTS whitelist (
                address TEXT PRIMARY KEY,
                added_at TEXT NOT NULL DEFAULT (datetime('now')),
                added_by TEXT
            );

            -- Positions table
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_address TEXT NOT NULL,
                token_id TEXT NOT NULL,
                market TEXT,
                side TEXT NOT NULL DEFAULT 'LONG',
                size REAL NOT NULL DEFAULT 0.0,
                avg_entry_price REAL NOT NULL DEFAULT 0.0,
                current_price REAL NOT NULL DEFAULT 0.0,
                unrealized_pnl REAL NOT NULL DEFAULT 0.0,
                cost_basis REAL NOT NULL DEFAULT 0.0,
                strategy TEXT,
                copied_from TEXT,
                opened_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_updated TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'open',
                UNIQUE(user_address, token_id, side)
            );

            -- Fund tables
            CREATE TABLE IF NOT EXISTS funds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_address TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                active INTEGER NOT NULL DEFAULT 1,
                total_aum REAL NOT NULL DEFAULT 0.0,
                nav_per_share REAL NOT NULL DEFAULT 1.0,
                total_shares REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS fund_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_id INTEGER NOT NULL REFERENCES funds(id),
                trader_address TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 0.0,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(fund_id, trader_address)
            );

            CREATE TABLE IF NOT EXISTS fund_investments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_id INTEGER NOT NULL REFERENCES funds(id),
                investor_address TEXT NOT NULL,
                amount_invested REAL NOT NULL,
                shares REAL NOT NULL,
                invested_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS fund_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_id INTEGER NOT NULL REFERENCES funds(id),
                date TEXT NOT NULL,
                nav REAL NOT NULL,
                daily_return REAL NOT NULL DEFAULT 0.0,
                cumulative_return REAL NOT NULL DEFAULT 0.0,
                UNIQUE(fund_id, date)
            );

            CREATE TABLE IF NOT EXISTS fund_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fund_id INTEGER NOT NULL REFERENCES funds(id),
                trade_id INTEGER REFERENCES trades(id),
                trader_address TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
            CREATE INDEX IF NOT EXISTS idx_trades_copied_from ON trades(copied_from);
            CREATE INDEX IF NOT EXISTS idx_seen_trade_ids_first_seen ON seen_trade_ids(first_seen);
            CREATE INDEX IF NOT EXISTS idx_sessions_nonce ON sessions(nonce);
            CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_address);
            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            CREATE INDEX IF NOT EXISTS idx_funds_owner ON funds(owner_address);
            CREATE INDEX IF NOT EXISTS idx_fund_alloc_fund ON fund_allocations(fund_id);
            CREATE INDEX IF NOT EXISTS idx_fund_invest_fund ON fund_investments(fund_id);
            CREATE INDEX IF NOT EXISTS idx_fund_invest_investor ON fund_investments(investor_address);
            CREATE INDEX IF NOT EXISTS idx_fund_perf_fund_date ON fund_performance(fund_id, date);
            CREATE INDEX IF NOT EXISTS idx_fund_trades_fund ON fund_trades(fund_id);
        """)

        _migrate_db(conn)

    return db_path


def _migrate_db(conn):
    """Run schema migrations."""
    cursor = conn.execute("PRAGMA table_info(followed_traders)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_address" not in columns:
        conn.execute(
            "ALTER TABLE followed_traders ADD COLUMN user_address TEXT DEFAULT 'legacy'"
        )

    for col, col_type in [
        ("copy_percentage", "REAL"),
        ("min_copy_size", "REAL"),
        ("max_copy_size", "REAL"),
        ("max_daily_spend", "REAL"),
    ]:
        if col not in columns:
            conn.execute(
                f"ALTER TABLE followed_traders ADD COLUMN {col} {col_type} DEFAULT NULL"
            )

    cursor = conn.execute("PRAGMA table_info(trades)")
    columns = [row[1] for row in cursor.fetchall()]

    if "user_address" not in columns:
        conn.execute(
            "ALTER TABLE trades ADD COLUMN user_address TEXT DEFAULT 'legacy'"
        )

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


# --- Whitelist Operations ---

def is_whitelisted(db_path: str, address: str) -> bool:
    """Check if an address is on the whitelist."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM whitelist WHERE address = ?", (address,)
        ).fetchone()
        return row is not None


def add_to_whitelist(db_path: str, address: str, added_by: str = "") -> bool:
    """Add an address to the whitelist. Returns True if added."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        try:
            conn.execute(
                "INSERT INTO whitelist (address, added_by) VALUES (?, ?)",
                (address, added_by.lower()),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def remove_from_whitelist(db_path: str, address: str) -> bool:
    """Remove an address from the whitelist."""
    address = address.lower().strip()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM whitelist WHERE address = ?", (address,)
        )
        return cursor.rowcount > 0


def get_whitelist(db_path: str) -> list[dict]:
    """Get all whitelisted addresses."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM whitelist ORDER BY added_at"
        ).fetchall()
        return [dict(r) for r in rows]


# --- User Operations ---

def create_or_get_user(db_path: str, address: str, role: str = "user") -> dict:
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
    address = address.lower().strip()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE address = ?", (address,)
        ).fetchone()
        return dict(row) if row else None


def create_session_nonce(db_path: str) -> str:
    nonce = secrets.token_hex(16)
    with _connect(db_path) as conn:
        conn.execute("INSERT INTO sessions (nonce) VALUES (?)", (nonce,))
    return nonce


def verify_session_nonce(db_path: str, nonce: str) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE nonce = ? AND verified = 0", (nonce,)
        ).fetchone()
        return row is not None


def mark_session_verified(db_path: str, nonce: str, address: str, token: str, expires_at: str):
    with _connect(db_path) as conn:
        conn.execute(
            """UPDATE sessions SET address = ?, token = ?, expires_at = ?, verified = 1
               WHERE nonce = ? AND verified = 0""",
            (address.lower(), token, expires_at, nonce),
        )


def cleanup_expired_sessions(db_path: str) -> int:
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE expires_at < datetime('now') OR "
            "(verified = 0 AND created_at < datetime('now', '-1 hour'))"
        )
        return cursor.rowcount


def claim_legacy_data(db_path: str, owner_address: str):
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
    db_path: str, strategy: str, token_id: str, side: str, amount: float,
    market: str = "", price: float = 0.0, expected_profit: float = 0.0,
    copied_from: str = "", original_trade_id: str = "", status: str = "executed",
    notes: str = "", user_address: Optional[str] = None,
) -> int:
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
    db_path: str, strategy: Optional[str] = None, limit: int = 50,
    user_address: Optional[str] = None,
) -> list[dict]:
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
    db_path: str, strategy: str = "copy", user_address: Optional[str] = None,
) -> float:
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
    db_path: str, strategy: Optional[str] = None,
    user_address: Optional[str] = None, days: int = 30,
) -> list[dict]:
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
            f"""SELECT date(timestamp) as date, COUNT(*) as trades,
                COALESCE(SUM(amount), 0) as spent,
                COALESCE(SUM(expected_profit), 0) as profit
            FROM trades WHERE {where}
            GROUP BY date(timestamp) ORDER BY date(timestamp) ASC""",
            params,
        ).fetchall()

        series = []
        cumulative = 0.0
        for row in rows:
            cumulative += row["profit"]
            series.append({
                "date": row["date"], "trades": row["trades"],
                "spent": round(row["spent"], 2), "profit": round(row["profit"], 2),
                "cumulative_profit": round(cumulative, 2),
            })
        return series


# --- Trader Operations ---

def add_trader(db_path: str, address: str, alias: str = "", user_address: Optional[str] = None) -> bool:
    address = address.lower().strip()
    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT 1 FROM followed_traders WHERE address = ? AND user_address = ? AND active = 1",
            (address, user_address),
        ).fetchone()
        if existing:
            return False
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


def remove_trader(db_path: str, address: str, user_address: Optional[str] = None) -> bool:
    address = address.lower().strip()
    with _connect(db_path) as conn:
        conditions = ["address = ?"]
        params = [address]
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        cursor = conn.execute(
            f"UPDATE followed_traders SET active = 0 WHERE {' AND '.join(conditions)}", params,
        )
        return cursor.rowcount > 0


def get_active_traders(db_path: str, user_address: Optional[str] = None) -> list[dict]:
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


def get_all_traders(db_path: str, user_address: Optional[str] = None) -> list[dict]:
    with _connect(db_path) as conn:
        if user_address:
            rows = conn.execute(
                "SELECT * FROM followed_traders WHERE user_address = ? ORDER BY active DESC, added_at",
                (user_address,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM followed_traders ORDER BY active DESC, added_at",
            ).fetchall()
        return [dict(r) for r in rows]


def update_trader_settings(db_path: str, address: str, user_address: str, **settings) -> bool:
    address = address.lower().strip()
    valid_keys = {"copy_percentage", "min_copy_size", "max_copy_size", "max_daily_spend", "active"}
    updates = []
    params = []
    for key, val in settings.items():
        if key in valid_keys:
            updates.append(f"{key} = ?")
            params.append(val)
    if not updates:
        return False
    params.extend([address, user_address])
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE followed_traders SET {', '.join(updates)} WHERE address = ? AND user_address = ?",
            params,
        )
        return cursor.rowcount > 0


def get_trader_daily_spend(db_path: str, trader_address: str, user_address: Optional[str] = None) -> float:
    today = date.today().isoformat()
    trader_address = trader_address.lower().strip()
    with _connect(db_path) as conn:
        conditions = ["strategy = 'copy'", "status = 'executed'", "date(timestamp) = ?", "copied_from = ?"]
        params: list = [today, trader_address]
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        where = " AND ".join(conditions)
        row = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as total FROM trades WHERE {where}", params,
        ).fetchone()
        return row["total"]


def update_trader_stats(db_path: str, address: str, amount_spent: float, user_address: Optional[str] = None):
    address = address.lower().strip()
    with _connect(db_path) as conn:
        conditions = ["address = ?"]
        params: list = [amount_spent, address]
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        conn.execute(
            f"""UPDATE followed_traders SET total_copied = total_copied + 1, total_spent = total_spent + ?
               WHERE {' AND '.join(conditions)}""",
            params,
        )


# --- Dedup Operations ---

def is_trade_seen(db_path: str, trade_id: str) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM seen_trade_ids WHERE trade_id = ?", (trade_id,)).fetchone()
        return row is not None


def mark_trade_seen(db_path: str, trade_id: str):
    with _connect(db_path) as conn:
        conn.execute("INSERT OR IGNORE INTO seen_trade_ids (trade_id) VALUES (?)", (trade_id,))


def cleanup_old_seen_trades(db_path: str, days: int = 7):
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM seen_trade_ids WHERE first_seen < datetime('now', ?)", (f"-{days} days",))


# --- Stats ---

def get_copy_stats(db_path: str, user_address: Optional[str] = None) -> dict:
    with _connect(db_path) as conn:
        conditions = ["strategy = 'copy'"]
        params = []
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        where = " AND ".join(conditions)
        row = conn.execute(
            f"""SELECT COUNT(*) as total_trades, COALESCE(SUM(amount), 0) as total_spent,
                COALESCE(SUM(CASE WHEN status = 'executed' THEN amount ELSE 0 END), 0) as total_executed,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) as failed_trades,
                COUNT(DISTINCT copied_from) as unique_traders_copied
               FROM trades WHERE {where}""",
            params,
        ).fetchone()
        return dict(row)


def get_arb_stats(db_path: str, user_address: Optional[str] = None) -> dict:
    with _connect(db_path) as conn:
        conditions = ["strategy = 'arbitrage'"]
        params = []
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        where = " AND ".join(conditions)
        row = conn.execute(
            f"""SELECT COUNT(*) as total_trades, COALESCE(SUM(amount), 0) as total_spent,
                COALESCE(SUM(expected_profit), 0) as total_expected_profit,
                COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) as failed_trades
               FROM trades WHERE {where}""",
            params,
        ).fetchone()
        return dict(row)


# --- Position Operations ---

def upsert_position(
    db_path: str, user_address: str, token_id: str, market: str,
    side: str, trade_amount: float, trade_price: float,
    strategy: str = "", copied_from: str = "",
) -> int:
    user_address = user_address.lower().strip() if user_address else "legacy"
    pos_side = "LONG" if side.upper() == "BUY" else "SHORT"

    with _connect(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM positions WHERE user_address = ? AND token_id = ? AND side = ? AND status = 'open'",
            (user_address, token_id, pos_side),
        ).fetchone()

        if existing:
            old_cost = existing["cost_basis"]
            old_size = existing["size"]

            if side.upper() == "BUY" and pos_side == "LONG":
                new_cost = old_cost + trade_amount
                new_size = old_size + (trade_amount / trade_price if trade_price > 0 else trade_amount)
                new_avg = new_cost / new_size if new_size > 0 else 0
            elif side.upper() == "SELL" and pos_side == "LONG":
                reduce_size = trade_amount / trade_price if trade_price > 0 else trade_amount
                new_size = max(0, old_size - reduce_size)
                new_cost = old_cost * (new_size / old_size) if old_size > 0 else 0
                new_avg = existing["avg_entry_price"]
            else:
                new_cost = old_cost + trade_amount
                new_size = old_size + (trade_amount / trade_price if trade_price > 0 else trade_amount)
                new_avg = new_cost / new_size if new_size > 0 else 0

            if new_size <= 0.001:
                conn.execute(
                    "UPDATE positions SET size = 0, cost_basis = 0, status = 'closed', last_updated = datetime('now') WHERE id = ?",
                    (existing["id"],),
                )
                return existing["id"]

            conn.execute(
                """UPDATE positions SET size = ?, avg_entry_price = ?, cost_basis = ?,
                    market = COALESCE(?, market), strategy = COALESCE(?, strategy),
                    last_updated = datetime('now') WHERE id = ?""",
                (new_size, new_avg, new_cost, market or None, strategy or None, existing["id"]),
            )
            return existing["id"]
        else:
            size = trade_amount / trade_price if trade_price > 0 else trade_amount
            cursor = conn.execute(
                """INSERT INTO positions
                   (user_address, token_id, market, side, size, avg_entry_price,
                    current_price, cost_basis, strategy, copied_from)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_address, token_id, market, pos_side, size, trade_price,
                 trade_price, trade_amount, strategy, copied_from),
            )
            return cursor.lastrowid


def get_open_positions(db_path: str, user_address: Optional[str] = None) -> list[dict]:
    with _connect(db_path) as conn:
        if user_address:
            rows = conn.execute(
                "SELECT * FROM positions WHERE user_address = ? AND status = 'open' ORDER BY unrealized_pnl DESC",
                (user_address,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM positions WHERE status = 'open' ORDER BY unrealized_pnl DESC",
            ).fetchall()
        return [dict(r) for r in rows]


def get_positions_summary(db_path: str, user_address: Optional[str] = None) -> dict:
    with _connect(db_path) as conn:
        conditions = ["status = 'open'"]
        params = []
        if user_address:
            conditions.append("user_address = ?")
            params.append(user_address)
        where = " AND ".join(conditions)
        row = conn.execute(
            f"""SELECT COUNT(*) as open_count,
                COALESCE(SUM(size * current_price), 0) as total_value,
                COALESCE(SUM(unrealized_pnl), 0) as unrealized_pnl
               FROM positions WHERE {where}""",
            params,
        ).fetchone()
        return dict(row)


def update_position_prices(db_path: str, updates: list[dict]):
    with _connect(db_path) as conn:
        for upd in updates:
            pos = conn.execute(
                "SELECT * FROM positions WHERE id = ? AND status = 'open'", (upd["id"],)
            ).fetchone()
            if not pos:
                continue
            current_price = upd["current_price"]
            if pos["side"] == "LONG":
                pnl = (current_price - pos["avg_entry_price"]) * pos["size"]
            else:
                pnl = (pos["avg_entry_price"] - current_price) * pos["size"]
            conn.execute(
                "UPDATE positions SET current_price = ?, unrealized_pnl = ?, last_updated = datetime('now') WHERE id = ?",
                (current_price, round(pnl, 2), upd["id"]),
            )


def close_position(db_path: str, position_id: int):
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE positions SET status = 'closed', size = 0, last_updated = datetime('now') WHERE id = ?",
            (position_id,),
        )


# --- Fund Operations ---

def create_fund(db_path: str, owner_address: str, name: str, description: str = "") -> int:
    owner_address = owner_address.lower().strip()
    with _connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO funds (owner_address, name, description) VALUES (?, ?, ?)",
            (owner_address, name, description),
        )
        return cursor.lastrowid


def get_fund(db_path: str, fund_id: int) -> Optional[dict]:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM funds WHERE id = ?", (fund_id,)).fetchone()
        return dict(row) if row else None


def get_funds(db_path: str, active_only: bool = True) -> list[dict]:
    with _connect(db_path) as conn:
        if active_only:
            rows = conn.execute("SELECT * FROM funds WHERE active = 1 ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM funds ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def update_fund(db_path: str, fund_id: int, owner_address: str, **kwargs) -> bool:
    updates = []
    params = []
    for key in ("name", "description", "active"):
        if key in kwargs:
            updates.append(f"{key} = ?")
            params.append(kwargs[key])
    if not updates:
        return False
    params.extend([fund_id, owner_address.lower()])
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE funds SET {', '.join(updates)} WHERE id = ? AND owner_address = ?", params,
        )
        return cursor.rowcount > 0


def set_fund_allocations(db_path: str, fund_id: int, allocations: list[dict]) -> None:
    with _connect(db_path) as conn:
        conn.execute("UPDATE fund_allocations SET active = 0 WHERE fund_id = ?", (fund_id,))
        for alloc in allocations:
            conn.execute(
                """INSERT INTO fund_allocations (fund_id, trader_address, weight, active)
                   VALUES (?, ?, ?, 1) ON CONFLICT(fund_id, trader_address)
                   DO UPDATE SET weight = excluded.weight, active = 1""",
                (fund_id, alloc["trader_address"].lower(), alloc["weight"]),
            )


def get_fund_allocations(db_path: str, fund_id: int) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM fund_allocations WHERE fund_id = ? AND active = 1 ORDER BY weight DESC",
            (fund_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def invest_in_fund(db_path: str, fund_id: int, investor_address: str, amount: float) -> dict:
    investor_address = investor_address.lower().strip()
    with _connect(db_path) as conn:
        fund = conn.execute("SELECT * FROM funds WHERE id = ? AND active = 1", (fund_id,)).fetchone()
        if not fund:
            raise ValueError("Fund not found or inactive")
        nav = fund["nav_per_share"]
        shares = amount / nav
        cursor = conn.execute(
            "INSERT INTO fund_investments (fund_id, investor_address, amount_invested, shares) VALUES (?, ?, ?, ?)",
            (fund_id, investor_address, amount, shares),
        )
        conn.execute(
            "UPDATE funds SET total_aum = total_aum + ?, total_shares = total_shares + ? WHERE id = ?",
            (amount, shares, fund_id),
        )
        row = conn.execute("SELECT * FROM fund_investments WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)


def withdraw_from_fund(db_path: str, investment_id: int, investor_address: str) -> float:
    investor_address = investor_address.lower().strip()
    with _connect(db_path) as conn:
        inv = conn.execute(
            "SELECT * FROM fund_investments WHERE id = ? AND investor_address = ? AND status = 'active'",
            (investment_id, investor_address),
        ).fetchone()
        if not inv:
            raise ValueError("Investment not found or already withdrawn")
        fund = conn.execute("SELECT * FROM funds WHERE id = ?", (inv["fund_id"],)).fetchone()
        withdrawal_amount = inv["shares"] * fund["nav_per_share"]
        conn.execute("UPDATE fund_investments SET status = 'withdrawn' WHERE id = ?", (investment_id,))
        conn.execute(
            "UPDATE funds SET total_aum = total_aum - ?, total_shares = total_shares - ? WHERE id = ?",
            (withdrawal_amount, inv["shares"], inv["fund_id"]),
        )
        return withdrawal_amount


def get_investor_investments(db_path: str, investor_address: str) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT fi.*, f.name as fund_name, f.nav_per_share, f.active as fund_active
               FROM fund_investments fi JOIN funds f ON fi.fund_id = f.id
               WHERE fi.investor_address = ? ORDER BY fi.invested_at DESC""",
            (investor_address.lower(),),
        ).fetchall()
        return [dict(r) for r in rows]


def record_fund_performance(db_path: str, fund_id: int, nav: float, daily_return: float, cumulative_return: float):
    today = date.today().isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """INSERT INTO fund_performance (fund_id, date, nav, daily_return, cumulative_return)
               VALUES (?, ?, ?, ?, ?) ON CONFLICT(fund_id, date) DO UPDATE SET
               nav = excluded.nav, daily_return = excluded.daily_return,
               cumulative_return = excluded.cumulative_return""",
            (fund_id, today, nav, daily_return, cumulative_return),
        )
        conn.execute("UPDATE funds SET nav_per_share = ? WHERE id = ?", (nav, fund_id))


def get_fund_performance(db_path: str, fund_id: int, days: int = 30) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM fund_performance WHERE fund_id = ? AND date >= date('now', ?)
               ORDER BY date ASC""",
            (fund_id, f"-{days} days"),
        ).fetchall()
        return [dict(r) for r in rows]


def record_fund_trade(db_path: str, fund_id: int, trade_id: int, trader_address: str, amount: float):
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO fund_trades (fund_id, trade_id, trader_address, amount) VALUES (?, ?, ?, ?)",
            (fund_id, trade_id, trader_address.lower(), amount),
        )


def get_fund_trades(db_path: str, fund_id: int, limit: int = 50) -> list[dict]:
    """Get recent trades executed by a fund, joined with trade details."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT ft.id, ft.fund_id, ft.trader_address, ft.amount, ft.timestamp,
                      t.token_id, t.side, t.market, t.status
               FROM fund_trades ft
               LEFT JOIN trades t ON ft.trade_id = t.id
               WHERE ft.fund_id = ?
               ORDER BY ft.timestamp DESC
               LIMIT ?""",
            (fund_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_fund_by_name(db_path: str, name: str) -> Optional[dict]:
    """Get a fund by its name."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM funds WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None
