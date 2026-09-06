"""SQLite 数据库：持仓、交易记录。"""

import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("FUND_ANALYZER_DB_PATH", str(DB_DIR / "portfolio.db")))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            fund_type TEXT DEFAULT '',
            buy_date TEXT NOT NULL,
            buy_amount REAL NOT NULL DEFAULT 0,
            buy_nav REAL NOT NULL DEFAULT 1,
            shares REAL NOT NULL DEFAULT 0,
            fee REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            is_sold INTEGER DEFAULT 0,
            sell_date TEXT,
            sell_amount REAL,
            sell_nav REAL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL UNIQUE,
            total_value REAL NOT NULL DEFAULT 0,
            total_cost  REAL NOT NULL DEFAULT 0,
            profit      REAL NOT NULL DEFAULT 0,
            profit_rate REAL NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


# Initialize DB on import
init_db()
