"""
数据库层 — 每个策略独立的 SQLite 数据库
=======================================
管理：账户信息、持仓、交易记录、净值历史
"""

import sqlite3
import os
from datetime import datetime

from ashare_quant_toolkit.config import DATA_DIR, INITIAL_CAPITAL


def get_strategy_db_path(strategy_id: str) -> str:
    """获取策略对应的数据库路径"""
    return os.path.join(DATA_DIR, f"{strategy_id}.db")


def get_conn(db_path):
    """获取数据库连接"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_strategy_db(db_path: str):
    """初始化策略数据库（创建表结构 + 种子账户）"""
    conn = get_conn(db_path)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS account (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        cash REAL NOT NULL,
        total_assets REAL NOT NULL,
        daily_pnl REAL DEFAULT 0,
        cumulative_return REAL DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL UNIQUE,
        stock_name TEXT NOT NULL,
        shares INTEGER NOT NULL,
        avg_cost REAL NOT NULL,
        current_price REAL NOT NULL,
        market_value REAL NOT NULL,
        pnl REAL DEFAULT 0,
        pnl_pct REAL DEFAULT 0,
        updated_at TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL,
        action TEXT NOT NULL,
        price REAL NOT NULL,
        shares INTEGER NOT NULL,
        amount REAL NOT NULL,
        commission REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        pnl REAL DEFAULT 0,
        reason TEXT DEFAULT ''
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS nav_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        total_assets REAL NOT NULL,
        cash REAL NOT NULL,
        market_value REAL NOT NULL,
        daily_pnl REAL DEFAULT 0,
        daily_return REAL DEFAULT 0,
        cumulative_return REAL DEFAULT 0
    )""")

    # 种子账户
    c.execute("SELECT COUNT(*) as cnt FROM account")
    if c.fetchone()["cnt"] == 0:
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute(
            "INSERT INTO account (date, cash, total_assets, cumulative_return) VALUES (?,?,?,?)",
            (today, INITIAL_CAPITAL, INITIAL_CAPITAL, 0.0),
        )

    conn.commit()
    conn.close()


def get_account(db_path: str) -> dict:
    """获取最新账户信息"""
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM account ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def update_account(db_path: str, date: str, cash: float, total_assets: float):
    """更新账户信息"""
    conn = get_conn(db_path)
    prev = conn.execute(
        "SELECT total_assets FROM account ORDER BY id DESC LIMIT 1"
    ).fetchone()
    prev_total = prev["total_assets"] if prev else INITIAL_CAPITAL
    daily_pnl = round(total_assets - prev_total, 2)
    cum_ret = round((total_assets / INITIAL_CAPITAL - 1) * 100, 2)
    conn.execute(
        "INSERT OR REPLACE INTO account (date, cash, total_assets, daily_pnl, cumulative_return) VALUES (?,?,?,?,?)",
        (date, cash, total_assets, daily_pnl, cum_ret),
    )
    conn.commit()
    conn.close()


def get_positions(db_path: str) -> list:
    """获取全部持仓"""
    conn = get_conn(db_path)
    rows = conn.execute("SELECT * FROM positions").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_position(db_path: str, code: str, name: str, shares: int,
                    avg_cost: float, current_price: float):
    """更新或插入持仓"""
    conn = get_conn(db_path)
    mv = round(shares * current_price, 2)
    pnl = round((current_price - avg_cost) * shares, 2)
    pnl_pct = round((current_price / avg_cost - 1) * 100, 2) if avg_cost > 0 else 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT OR REPLACE INTO positions 
        (stock_code, stock_name, shares, avg_cost, current_price, market_value, pnl, pnl_pct, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (code, name, shares, avg_cost, current_price, mv, pnl, pnl_pct, now),
    )
    conn.commit()
    conn.close()


def clear_position(db_path: str, code: str):
    """清空指定持仓"""
    conn = get_conn(db_path)
    conn.execute("DELETE FROM positions WHERE stock_code=?", (code,))
    conn.commit()
    conn.close()


def record_trade(db_path: str, code: str, name: str, action: str,
                 price: float, shares: int, amount: float,
                 commission: float, tax: float, pnl: float, reason: str):
    """记录一笔交易"""
    conn = get_conn(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO trades (trade_date, stock_code, stock_name, action, price, shares, amount, commission, tax, pnl, reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (now, code, name, action, price, shares, amount, commission, tax, pnl, reason),
    )
    conn.commit()
    conn.close()


def save_nav(db_path: str, date: str, total_assets: float, cash: float,
             market_value: float, daily_pnl: float, daily_return: float,
             cum_return: float):
    """保存净值快照"""
    conn = get_conn(db_path)
    conn.execute(
        """INSERT OR REPLACE INTO nav_history 
        (date, total_assets, cash, market_value, daily_pnl, daily_return, cumulative_return)
        VALUES (?,?,?,?,?,?,?)""",
        (date, total_assets, cash, market_value, daily_pnl, daily_return, cum_return),
    )
    conn.commit()
    conn.close()


def get_nav_history(db_path: str) -> list:
    """获取全部净值历史"""
    conn = get_conn(db_path)
    rows = conn.execute("SELECT * FROM nav_history ORDER BY date").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade_history(db_path: str, limit: int = 100) -> list:
    """获取近期交易记录"""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM trades ORDER BY trade_date DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_trades(db_path: str, date: str) -> list:
    """获取今日交易记录"""
    conn = get_conn(db_path)
    rows = conn.execute(
        "SELECT * FROM trades WHERE trade_date LIKE ?", (f"{date}%",)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
