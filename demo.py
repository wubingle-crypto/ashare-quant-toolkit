#!/usr/bin/env python3
"""
A股量化工具箱 · 2行代码获取实时行情 DEMO
========================================

演示如何用最简代码获取 A 股实时行情数据。

用法:
    python demo.py

示例输出:
    平安银行    000001  11.25  +0.72%
    贵州茅台    600519  1893.00  +1.23%
    ...
"""

# ── 第1行：引入数据获取模块 ──
from ashare_quant_toolkit.data_fetcher import fetch_tencent_realtime_as_df

# ── 第2行：获取实时行情（传入股票代码列表） ──
df = fetch_tencent_realtime_as_df(["000001", "000333", "000858", "002594", "600519", "600036", "601318", "000725"])

# ── 展示结果 ──
if not df.empty:
    df_display = df[["code", "name", "close", "change_pct", "volume", "high", "low"]].copy()
    df_display["change_pct"] = df_display["change_pct"].map(lambda x: f"{x:+.2f}%")
    df_display["close"] = df_display["close"].map(lambda x: f"{x:.2f}")
    df_display["volume"] = df_display["volume"].map(lambda x: f"{x/1e8:.2f}亿" if x > 1e8 else f"{x/1e4:.0f}万")
    print("\n📊 A股实时行情\n" + "=" * 50)
    print(df_display.to_string(index=False))
else:
    print("⚠️  获取行情失败（非交易时间或网络问题）")
    print("💡 提示：A股交易时间为周一至周五 09:30-15:00")
