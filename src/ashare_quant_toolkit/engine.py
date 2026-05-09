"""
交易引擎
========
手续费计算、买入/卖出执行、技术指标丰富、日终结算
"""

import time
from datetime import datetime

import pandas as pd
import numpy as np

from ashare_quant_toolkit.config import (
    INITIAL_CAPITAL, COMMISSION_RATE, STAMP_TAX_RATE,
    MIN_COMMISSION, TRADE_UNIT, VALIDATED_STOCK_POOL,
    CODE_TO_NAME, STRATEGIES,
)
from ashare_quant_toolkit.db import (
    get_strategy_db_path, init_strategy_db, get_account, get_positions,
    update_position, clear_position, record_trade,
    update_account, save_nav,
)
from ashare_quant_toolkit.data_fetcher import (
    fetch_tencent_realtime_as_df, get_stock_history,
)


# ──────────────────────────────────────────────
# 交易成本计算
# ──────────────────────────────────────────────

def calc_trade_cost(price, shares, is_buy=True):
    """计算交易成本"""
    amount = price * shares
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    stamp_tax = amount * STAMP_TAX_RATE if not is_buy else 0
    return round(commission, 2), round(stamp_tax, 2), round(amount, 2)


# ──────────────────────────────────────────────
# 交易执行
# ──────────────────────────────────────────────

def exec_buy(db_path, code, name, price, shares, reason, max_pos):
    """执行买入操作"""
    if shares % TRADE_UNIT != 0:
        shares = (shares // TRADE_UNIT) * TRADE_UNIT
    if shares < 100:
        return False, "数量不足"

    from ashare_quant_toolkit.config import is_allowed_stock
    if not is_allowed_stock(code):
        return False, f"不允许交易 {code}"

    comm, tax, amount = calc_trade_cost(price, shares, is_buy=True)
    total_cost = amount + comm + tax

    acct = get_account(db_path)
    if not acct or acct["cash"] < total_cost:
        return False, f"现金不足 (需{total_cost:,.0f}, 有{acct['cash']:,.0f})"

    positions = get_positions(db_path)
    existing = [p for p in positions if p["stock_code"] == code]
    if not existing and len(positions) >= max_pos:
        return False, f"持仓已满({max_pos}只)"

    if existing:
        old = existing[0]
        ts = old["shares"] + shares
        tc = old["avg_cost"] * old["shares"] + amount
        new_avg = round(tc / ts, 3)
        update_position(db_path, code, name, ts, new_avg, price)
    else:
        update_position(db_path, code, name, shares, price, price)

    record_trade(db_path, code, name, "买入", price, shares, amount, comm, tax, 0, reason)
    new_cash = round(acct["cash"] - total_cost, 2)
    total_mv = sum(p["market_value"] for p in get_positions(db_path))
    update_account(db_path, datetime.now().strftime("%Y-%m-%d"), new_cash, new_cash + total_mv)
    return True, f"买入 {name}({code}) {shares}股 @{price:.2f}"


def exec_sell(db_path, code, name, price, shares, reason):
    """执行卖出操作"""
    positions = get_positions(db_path)
    pos = next((p for p in positions if p["stock_code"] == code), None)
    if not pos:
        return False, "无持仓"

    actual = min(shares, pos["shares"])
    comm, tax, amount = calc_trade_cost(price, actual, is_buy=False)
    pnl = round((price - pos["avg_cost"]) * actual, 2)

    acct = get_account(db_path)
    record_trade(db_path, code, name, "卖出", price, actual, amount, comm, tax, pnl, reason)
    income = round(amount - comm - tax, 2)
    new_cash = round(acct["cash"] + income, 2)

    remaining = pos["shares"] - actual
    if remaining <= 0:
        clear_position(db_path, code)
    else:
        update_position(db_path, code, name, remaining, pos["avg_cost"], price)

    new_positions = get_positions(db_path)
    total_mv = sum(p["market_value"] for p in new_positions)
    update_account(db_path, datetime.now().strftime("%Y-%m-%d"), new_cash, new_cash + total_mv)
    return True, f"卖出 {name}({code}) {actual}股 @{price:.2f} PnL:{pnl:+.2f}"


# ──────────────────────────────────────────────
# 技术指标丰富（为策略提供所需的行情衍生数据）
# ──────────────────────────────────────────────

def enrich_indicators(prices_df):
    """
    为实时行情 DataFrame 添加技术指标
    使用 akshare 获取历史数据计算均线、量比、距高/低点距离等

    Parameters
    ----------
    prices_df : pd.DataFrame
        必须包含 code 和 close 列

    Returns
    -------
    pd.DataFrame
        添加了 m5, m60, m60_ret, vol_ratio, above_ma60, hhv60 等列
    """
    if prices_df is None or prices_df.empty:
        return prices_df

    codes = prices_df["code"].tolist()
    today_str = datetime.now().strftime("%Y-%m-%d")

    for idx, row in prices_df.iterrows():
        code = row["code"]
        try:
            df = get_stock_history(code, start_date="20250101", end_date=today_str)
            if df is not None and len(df) >= 30:
                close = df["close"].values.astype(float)
                volume = df["volume"].values.astype(float)
                high = df["high"].values.astype(float)

                ma20 = pd.Series(close).rolling(20).mean().values[-1]
                ma60 = pd.Series(close).rolling(60).mean().values[-1]
                hhv60 = pd.Series(high).rolling(60).max().values[-1]
                vol20 = pd.Series(volume).rolling(20).mean().values[-1]

                if hhv60 > 0:
                    prices_df.at[idx, "m60"] = round((row["close"] / hhv60 - 1) * 100, 2)
                else:
                    prices_df.at[idx, "m60"] = 0

                if len(close) >= 5:
                    prices_df.at[idx, "m5"] = round((close[-1] / close[-6] - 1) * 100, 2)
                if len(close) >= 60:
                    prices_df.at[idx, "m60_ret"] = round((close[-1] / close[-60] - 1) * 100, 2)

                prices_df.at[idx, "above_ma60"] = row["close"] > ma60

                if vol20 > 0:
                    prices_df.at[idx, "vol_ratio"] = round(row["volume"] / vol20, 2)
                else:
                    prices_df.at[idx, "vol_ratio"] = 1

                prices_df.at[idx, "hhv60"] = hhv60

            time.sleep(0.15)  # 限速
        except Exception:
            prices_df.at[idx, "vol_ratio"] = 1
            prices_df.at[idx, "m5"] = 0
            prices_df.at[idx, "m60"] = 0
            prices_df.at[idx, "m60_ret"] = 0
            prices_df.at[idx, "above_ma60"] = False
            prices_df.at[idx, "hhv60"] = row["close"]
            continue

    return prices_df


# ──────────────────────────────────────────────
# 日终结算
# ──────────────────────────────────────────────

def daily_settlement(db_path):
    """
    日终结算：用最新行情更新所有持仓市值和净值
    """
    today = datetime.now().strftime("%Y-%m-%d")
    acct = get_account(db_path)
    positions = get_positions(db_path)

    codes = [p["stock_code"] for p in positions]
    all_prices = {}
    if codes:
        from ashare_quant_toolkit.data_fetcher import fetch_tencent_realtime
        result = fetch_tencent_realtime(codes)
        if isinstance(result, dict):
            all_prices = result

    total_mv = 0
    for pos in positions:
        price_data = all_prices.get(pos["stock_code"], {})
        new_price = price_data.get("close", pos["current_price"]) if price_data else pos["current_price"]
        mv = round(pos["shares"] * new_price, 2)
        pnl = round((new_price - pos["avg_cost"]) * pos["shares"], 2)
        pnl_pct = round((new_price / pos["avg_cost"] - 1) * 100, 2) if pos["avg_cost"] > 0 else 0
        update_position(db_path, pos["stock_code"], pos["stock_name"],
                        pos["shares"], pos["avg_cost"], new_price)
        total_mv += mv

    cash = acct["cash"] if acct else INITIAL_CAPITAL
    total_assets = cash + total_mv
    prev_assets = acct["total_assets"] if acct else INITIAL_CAPITAL
    daily_pnl = round(total_assets - prev_assets, 2)
    daily_ret = round(daily_pnl / prev_assets * 100, 2) if prev_assets > 0 else 0
    cum_ret = round((total_assets / INITIAL_CAPITAL - 1) * 100, 2)

    update_account(db_path, today, cash, total_assets)
    save_nav(db_path, today, total_assets, cash, total_mv, daily_pnl, daily_ret, cum_ret)

    return {
        "cash": cash,
        "total_assets": total_assets,
        "market_value": total_mv,
        "daily_pnl": daily_pnl,
        "daily_return": daily_ret,
        "cumulative_return": cum_ret,
    }


# ──────────────────────────────────────────────
# 策略运行入口
# ──────────────────────────────────────────────

def run_strategy(strategy_id, strategy_func):
    """
    运行单个策略的盘中交易

    Parameters
    ----------
    strategy_id : str
        策略ID（如 'surge', 'double_vol' 等）
    strategy_func : callable
        信号生成函数，签名：func(prices_df, positions, acct, cfg) -> {'buy': [...], 'sell': [...]}

    Returns
    -------
    dict
        运行结果，包含 strategy, trades, settlement, positions 等
    """
    cfg = STRATEGIES[strategy_id]
    db_path = get_strategy_db_path(strategy_id)
    init_strategy_db(db_path)

    # 获取实时行情
    prices_df = fetch_tencent_realtime_as_df(list(VALIDATED_STOCK_POOL.values()))

    if prices_df.empty:
        return {"strategy": cfg["name"], "trades": 0, "error": "无法获取行情"}

    # 添加技术指标（等权全池和AI量化自行计算）
    if strategy_id not in ("equal", "ai_quant"):
        prices_df = enrich_indicators(prices_df)

    acct = get_account(db_path)
    if not acct:
        return {"strategy": cfg["name"], "trades": 0, "error": "账户不存在"}

    positions = get_positions(db_path)

    # 生成信号
    signals = strategy_func(prices_df, positions, acct, cfg)

    # 执行交易
    trades = []
    for code, name, price, shares, reason in signals.get("sell", []):
        ok, msg = exec_sell(db_path, code, name, price, shares, reason)
        trades.append(("sell", ok, msg))
    for code, name, price, shares, reason in signals.get("buy", []):
        ok, msg = exec_buy(db_path, code, name, price, shares, reason, cfg["max_positions"])
        trades.append(("buy", ok, msg))

    # 日终结算
    settlement = daily_settlement(db_path)

    return {
        "strategy": cfg["name"],
        "emoji": cfg["emoji"],
        "trades": len(trades),
        "trade_details": trades,
        "settlement": settlement,
        "positions": get_positions(db_path),
    }
