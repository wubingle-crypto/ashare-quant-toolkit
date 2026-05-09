"""
策略1: 放量上攻 (Surge)
======================
核心逻辑：成交量 > 1.5倍均量 + 上涨 → 追量价爆发
优先选择量比大且涨幅高的股票
"""

import sys
import os

import pandas as pd
import numpy as np

from ashare_quant_toolkit.config import CODE_TO_NAME


def generate_signals(prices_df, positions, account, config):
    """
    放量上攻信号生成

    逻辑：
    1. 量比 > 1.5 且涨幅 > 0 → 量价齐升信号
    2. 量比 > 2 → 放量信号（不论涨跌）
    3. 5日动量加成
    4. 取 TOP N 买入，卖出量能衰退的持仓
    """
    signals = {"buy": [], "sell": []}
    max_pos = config["max_positions"]

    if prices_df is None or prices_df.empty:
        return signals

    scored = []
    for _, row in prices_df.iterrows():
        code = row.get("code", "")
        if not code:
            continue
        price = row.get("close", 0)
        if price <= 0:
            continue
        vol_ratio = row.get("vol_ratio", 1)
        change_pct = row.get("change_pct", 0)
        m5 = row.get("m5", 0)

        if vol_ratio > 1.5 and change_pct > 0:
            score = vol_ratio * change_pct
        elif vol_ratio > 2:
            score = -vol_ratio * abs(change_pct)
        else:
            score = change_pct * 0.5

        if change_pct > 0 and m5 > 0:
            score += m5 * 0.3

        name = CODE_TO_NAME.get(code, row.get("name", code))
        scored.append((code, name, price, score))

    scored.sort(key=lambda x: -x[3])
    top = {s[0] for s in scored[:max_pos] if s[3] > 0}

    # 卖出：不再在 TOP 中的持仓
    for pos in positions:
        if pos["stock_code"] not in top:
            cur = pos["current_price"]
            if cur > 0:
                signals["sell"].append(
                    (pos["stock_code"], pos["stock_name"], cur, pos["shares"], "量能衰退")
                )

    # 买入
    cash = account["cash"]
    remaining = max_pos - len(positions) + len(signals["sell"])
    for code, name, price, score in scored[:max_pos]:
        if code in [p["stock_code"] for p in positions]:
            continue
        if len(signals["buy"]) >= remaining:
            break
        cp = cash / max(remaining, 1)
        sh = int(cp / price / 100) * 100
        if sh >= 100:
            signals["buy"].append((code, name, price, sh, f"量价{score:.1f}"))

    return signals


def run():
    """独立运行此策略"""
    from ashare_quant_toolkit.engine import run_strategy
    result = run_strategy("surge", generate_signals)
    st = result.get("settlement", {})
    print(f"🔥 放量上攻: ¥{st.get('total_assets', 0):,.0f} | "
          f"{st.get('cumulative_return', 0):+.2f}% | "
          f"持仓{len(result.get('positions', []))}只")
    return result


if __name__ == "__main__":
    run()
