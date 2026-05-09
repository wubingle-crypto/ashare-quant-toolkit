"""
竞赛运行器 — 5策略每日同台竞技
===============================
运行所有策略并输出排名
"""

from datetime import datetime

from ashare_quant_toolkit.config import STRATEGIES
from ashare_quant_toolkit.engine import run_strategy
from ashare_quant_toolkit.strategies import (
    surge,
    double_vol,
    equal,
    reversal,
    ai_quant,
)

# 策略ID到信号函数的映射
STRATEGY_SIGNAL_FUNCS = {
    "surge": surge.generate_signals,
    "double_vol": double_vol.generate_signals,
    "equal": equal.generate_signals,
    "reversal": reversal.generate_signals,
    "ai_quant": ai_quant.generate_signals,
}


def run_all():
    """运行全部5个策略，输出排名"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🏆 A股量化工具箱 — 多策略竞赛 — {today}")
    print("=" * 60)

    results = []
    for sid, cfg in STRATEGIES.items():
        print(f"\n▶ {cfg['emoji']} {cfg['name']}...")
        try:
            signal_func = STRATEGY_SIGNAL_FUNCS[sid]
            result = run_strategy(sid, signal_func)
            results.append(result)
            st = result.get("settlement", {})
            print(f"  ¥{st.get('total_assets', 0):,.0f} | "
                  f"{st.get('cumulative_return', 0):+.2f}% | "
                  f"持仓{len(result.get('positions', []))}只")
        except Exception as e:
            print(f"  ❌ {e}")
            results.append({"strategy": cfg["name"], "error": str(e)})

    # 排名
    results_sorted = [r for r in results if "settlement" in r]
    results_sorted.sort(key=lambda x: -x["settlement"]["total_assets"])

    print(f"\n{'=' * 60}")
    print("📊 策略排名:")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
    for rank, r in enumerate(results_sorted):
        medal = medals[rank]
        st = r["settlement"]
        print(f"  {medal} {r.get('emoji', '')} {r['strategy']}: "
              f"¥{st['total_assets']:,.0f} ({st['cumulative_return']:+.2f}%)")

    return results


def main():
    run_all()


if __name__ == "__main__":
    main()
