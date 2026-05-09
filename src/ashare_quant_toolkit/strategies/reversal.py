"""
策略4: 反转猎人 (Reversal Hunter)
=================================
核心逻辑：买超跌股 — 短期跌幅大 + 接近近期低点 + 缩量
"""

import pandas as pd
import numpy as np

from ashare_quant_toolkit.config import CODE_TO_NAME


def generate_signals(prices_df, positions, account, config):
    """
    反转猎人信号生成

    逻辑：
    1. 5日跌幅 > 3% → 加分
    2. 60日收益 < -10% → 加分（中期超跌）
    3. 价格在60日高点的95%以下 → 加分（非追高）
    4. 量比 < 0.7 → 加分（缩量企稳）
    5. 5日跌幅 > -8% → 加分（避免极端暴跌）
    6. 持仓获利 > 15% 卖出；反转失效卖出
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
        m5 = row.get("m5", 0)
        m60_ret = row.get("m60_ret", 0)
        hhv60 = row.get("hhv60", price)
        vol_ratio = row.get("vol_ratio", 1)
        name = CODE_TO_NAME.get(code, row.get("name", code))

        score = 50
        if m5 < -3:
            score += 15
        if m60_ret < -10:
            score += 10
        if hhv60 > 0 and price / hhv60 < 0.95:
            score += 15
        if vol_ratio < 0.7:
            score += 10
        if m5 > -8:
            score += 5

        scored.append((code, name, price, score, m5))

    scored.sort(key=lambda x: -x[3])
    target = {s[0] for s in scored[:max_pos]}

    # 卖出
    for pos in positions:
        cur = pos["current_price"]
        if cur <= 0:
            continue
        gain = (cur / pos["avg_cost"] - 1) * 100
        if gain > 15:
            signals["sell"].append(
                (pos["stock_code"], pos["stock_name"], cur, pos["shares"], "反转获利")
            )
        elif pos["stock_code"] not in target:
            match = [s for s in scored if s[0] == pos["stock_code"]]
            if match and match[0][3] < 50:
                signals["sell"].append(
                    (pos["stock_code"], pos["stock_name"], cur, pos["shares"], "反转失效")
                )

    # 买入
    cash = account["cash"]
    remaining = max_pos - len(positions) + len(signals["sell"])
    for code, name, price, score, m5 in scored[:max_pos]:
        if code in [p["stock_code"] for p in positions]:
            continue
        if len(signals["buy"]) >= remaining:
            break
        cp = cash / max(remaining, 1)
        sh = int(cp / price / 100) * 100
        if sh >= 100:
            signals["buy"].append((code, name, price, sh, f"超跌{m5:+.1f}%/{score}分"))

    return signals


def run():
    """独立运行此策略"""
    from ashare_quant_toolkit.engine import run_strategy
    result = run_strategy("reversal", generate_signals)
    st = result.get("settlement", {})
    print(f"🔄 反转猎人: ¥{st.get('total_assets', 0):,.0f} | "
          f"{st.get('cumulative_return', 0):+.2f}% | "
          f"持仓{len(result.get('positions', []))}只")
    return result


if __name__ == "__main__":
    run()
