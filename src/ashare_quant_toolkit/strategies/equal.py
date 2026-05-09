"""
策略3: 等权全池 (Equal Weight)
==============================
核心逻辑：等权买入全部股票，被动持有，定期再平衡
"""

import pandas as pd
import numpy as np

from ashare_quant_toolkit.config import CODE_TO_NAME


def generate_signals(prices_df, positions, account, config):
    """
    等权全池信号生成

    逻辑：
    1. 全部股票等权重配置
    2. 持仓超过目标权重2倍时卖出超配部分
    3. 现金足够时买入未持仓的股票
    """
    signals = {"buy": [], "sell": []}

    if prices_df is None or prices_df.empty:
        return signals

    n_stocks = len(prices_df)
    if n_stocks == 0:
        return signals
    target_w = 1.0 / n_stocks

    # 卖出超配
    sell_set = set()
    for pos in positions:
        mv = pos["shares"] * pos["current_price"]
        total = account["cash"] + sum(
            p["shares"] * p["current_price"] for p in positions
        )
        if total > 0 and mv / total > target_w * 2:
            excess = (mv / total - target_w) / (mv / total)
            sell_sh = int(pos["shares"] * excess / 100) * 100
            if sell_sh >= 100:
                signals["sell"].append(
                    (pos["stock_code"], pos["stock_name"], pos["current_price"],
                     sell_sh, "再平衡")
                )
                sell_set.add(pos["stock_code"])

    # 买入（等权配置）
    if account["cash"] > 10000:
        per_stock = min(account["cash"] / n_stocks, account["cash"] / 10)
        for _, row in prices_df.iterrows():
            code = row.get("code", "")
            if code in sell_set or code in [p["stock_code"] for p in positions]:
                continue
            if len(signals["buy"]) >= 10:
                break
            price = row.get("close", 0)
            if price <= 0:
                continue
            name = CODE_TO_NAME.get(code, row.get("name", code))
            sh = int(per_stock / price / 100) * 100
            if sh >= 100:
                signals["buy"].append((code, name, price, sh, "等权配置"))

    return signals


def run():
    """独立运行此策略"""
    from ashare_quant_toolkit.engine import run_strategy
    result = run_strategy("equal", generate_signals)
    st = result.get("settlement", {})
    print(f"📅 等权全池: ¥{st.get('total_assets', 0):,.0f} | "
          f"{st.get('cumulative_return', 0):+.2f}% | "
          f"持仓{len(result.get('positions', []))}只")
    return result


if __name__ == "__main__":
    run()
