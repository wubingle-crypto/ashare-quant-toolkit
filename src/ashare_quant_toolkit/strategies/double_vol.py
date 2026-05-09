"""
策略2: 倍量抄底逃顶 (Double Volume)
==================================
核心逻辑：左倍量抄底 + 右倍量逃顶
成交量突然翻倍时，判断方向：
- 低位放量上涨 → 抄底买入
- 高位放量上涨 → 出货卖出
"""

import os
import json
from datetime import datetime

import pandas as pd
import numpy as np

from ashare_quant_toolkit.config import DATA_DIR, CODE_TO_NAME

# 盘中持久化的前日成交量缓存
_PREV_VOLS_FILE = os.path.join(DATA_DIR, "prev_vols.json")


def _load_prev_vols():
    try:
        with open(_PREV_VOLS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_prev_vols(vols):
    os.makedirs(os.path.dirname(_PREV_VOLS_FILE), exist_ok=True)
    with open(_PREV_VOLS_FILE, "w") as f:
        json.dump(vols, f)


def generate_signals(prices_df, positions, account, config):
    """
    倍量抄底逃顶信号生成

    逻辑：
    1. 量比 >= 2.0 视为"倍量"信号
    2. 低位放量上涨 → 抄底买入（距60日高点回落 > 30%）
    3. 高位放量上涨 → 追强买入（涨幅大且站上60日线）
    4. 持仓股高位放量上涨 → 出货卖出
    5. 持仓股深亏止损
    """
    signals = {"buy": [], "sell": []}
    max_pos = config["max_positions"]

    if prices_df is None or prices_df.empty:
        return signals

    prev_vols = _load_prev_vols()

    buy_candidates = []
    sell_list = []

    for _, row in prices_df.iterrows():
        code = row.get("code", "")
        if not code:
            continue
        price = row.get("close", 0)
        if price <= 0:
            continue

        cur_vol = row.get("volume", 0)
        prev_vol = prev_vols.get(code, 0)
        vol_ratio = cur_vol / prev_vol if prev_vol > 0 else 0
        change_pct = row.get("change_pct", 0)
        m60 = row.get("m60", 0)
        m60_ret = row.get("m60_ret", 0)
        above_ma60 = row.get("above_ma60", False)
        name = CODE_TO_NAME.get(code, row.get("name", code))

        is_double = vol_ratio >= 2.0
        if not is_double:
            continue

        # 买入信号
        if change_pct > 0:
            is_oversold = m60 <= -30 and not above_ma60
            is_strong = change_pct >= 1.5 and above_ma60
            if is_oversold:
                score = abs(m60) * 0.5 + change_pct * 0.5
                buy_candidates.append(
                    (code, name, price, score, f"抄底(回落{abs(m60):.0f}%)")
                )
            elif is_strong:
                score = change_pct * 1.0 + abs(m60) * 0.3
                buy_candidates.append(
                    (code, name, price, score, f"追强(涨{change_pct:+.1f}%)")
                )

        # 卖出信号
        held = [p["stock_code"] for p in positions]
        if code in held:
            pos = next(p for p in positions if p["stock_code"] == code)
            is_overbought = m60_ret >= 50 and above_ma60
            if is_overbought:
                if change_pct > 0 and change_pct < 1.5:
                    sell_list.append(
                        (code, name, price, pos["shares"], f"出货(涨{change_pct:+.1f}%放量)")
                    )
                elif change_pct < -3:
                    gain = (price / pos["avg_cost"] - 1) * 100
                    if gain < -15:
                        sell_list.append(
                            (code, name, price, pos["shares"], f"深亏止损({gain:+.1f}%)")
                        )

    # 更新成交量缓存
    current_vols = {}
    for _, row in prices_df.iterrows():
        current_vols[row.get("code", "")] = row.get("volume", 0)
    _save_prev_vols(current_vols)

    buy_candidates.sort(key=lambda x: -x[3])
    signals["sell"] = sell_list

    remaining = max_pos - len(positions) + len(sell_list)
    for code, name, price, score, reason in buy_candidates[:remaining]:
        if code in [p["stock_code"] for p in positions]:
            continue
        if len(signals["buy"]) >= remaining:
            break
        cp = account["cash"] / max(remaining, 1)
        sh = int(cp / price / 100) * 100
        if sh >= 100:
            signals["buy"].append((code, name, price, sh, reason))

    return signals


def run():
    """独立运行此策略"""
    from ashare_quant_toolkit.engine import run_strategy
    result = run_strategy("double_vol", generate_signals)
    st = result.get("settlement", {})
    print(f"📊 倍量抄底逃顶: ¥{st.get('total_assets', 0):,.0f} | "
          f"{st.get('cumulative_return', 0):+.2f}% | "
          f"持仓{len(result.get('positions', []))}只")
    return result


if __name__ == "__main__":
    run()
