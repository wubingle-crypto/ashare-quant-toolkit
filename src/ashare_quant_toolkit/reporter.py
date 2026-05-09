"""
投资研报生成器
==============
每日生成完整的 HTML 投资研报
包含：大盘分析、板块热度、个股扫描、策略PK排名
"""

import os
import base64
import time
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from ashare_quant_toolkit.config import (
    REPORTS_DIR, DATA_DIR, INITIAL_CAPITAL,
    VALIDATED_STOCK_POOL, SECTOR_MAP, STOCK_POOL,
    STRATEGIES, CODE_TO_NAME,
)
from ashare_quant_toolkit.db import (
    get_strategy_db_path, get_account, get_positions,
    get_nav_history, get_today_trades,
)
from ashare_quant_toolkit.data_fetcher import (
    fetch_tencent_realtime, get_market_index,
)
import subprocess

# ── 颜色方案（A股绿涨红跌） ──
GREEN = "#ef4444"
RED = "#22c55e"
BLUE = "#3b82f6"
YELLOW = "#eab308"
NEUTRAL = "#9ca3af"
BG = "#0f172a"
CARD = "#1e293b"

# ── 中文字体 ──
_ZH_FONTS = [
    "/usr/share/fonts/google-droid/DroidSansFallback.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
for _f in _ZH_FONTS:
    if os.path.exists(_f):
        fm.fontManager.addfont(_f)
        plt.rcParams["font.sans-serif"] = [os.path.basename(_f).split(".")[0], "DejaVu Sans"]
        break
else:
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ──────────────────────────────────────────────
# 数据获取
# ──────────────────────────────────────────────

def fetch_market_indices():
    """获取三大指数实时数据"""
    indices = {}
    sym_map = {"上证指数": "sh000001", "沪深300": "sh000300", "中证500": "sh000905"}
    symbols = ",".join(sym_map.values())
    url = f"http://qt.gtimg.cn/q={symbols}"
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "8", url],
            capture_output=True, timeout=12,
        )
        text = r.stdout.decode("gbk", errors="replace")
        for line in text.strip().split("\n"):
            if "=" not in line:
                continue
            name, data = line.split("=", 1)
            data = data.strip('" ;\n').split("~")
            if len(data) < 40:
                continue
            for cn_name, sym in sym_map.items():
                if sym in name:
                    indices[cn_name] = {
                        "price": float(data[3]) if data[3] else 0,
                        "change_pct": float(data[32]) if data[32] else 0,
                        "volume": int(data[6]) if data[6] and data[6].isdigit() else 0,
                        "high": float(data[33]) if data[33] else 0,
                        "low": float(data[34]) if data[34] else 0,
                        "open": float(data[5]) if data[5] else 0,
                    }
    except Exception:
        pass
    return indices


def fetch_all_stocks_data():
    """获取全部股票实时数据"""
    codes = list(VALIDATED_STOCK_POOL.values())
    symbols = []
    cmap = {}
    for c in codes:
        pfx = "sh" if c.startswith("6") else "sz"
        sym = f"{pfx}{c}"
        symbols.append(sym)
        cmap[sym] = c
    url = f"http://qt.gtimg.cn/q={','.join(symbols)}"
    result = {}
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "12", url],
            capture_output=True, timeout=18,
        )
        text = r.stdout.decode("gbk", errors="replace")
        for line in text.strip().split("\n"):
            if "=" not in line:
                continue
            name, data = line.split("=", 1)
            data = data.strip('" ;\n').split("~")
            if len(data) < 40:
                continue
            for sym, code in cmap.items():
                if sym in name:
                    result[code] = {
                        "code": code,
                        "name": CODE_TO_NAME.get(code, data[1]),
                        "close": float(data[3]) if data[3] else 0,
                        "prev_close": float(data[4]) if data[4] else 0,
                        "open": float(data[5]) if data[5] else 0,
                        "volume": int(float(data[6])) if data[6] else 0,
                        "high": float(data[33]) if data[33] else 0,
                        "low": float(data[34]) if data[34] else 0,
                        "change_pct": float(data[32]) if data[32] else 0,
                        "amount": float(data[37]) if data[37] else 0,
                    }
    except Exception:
        pass
    return result


# ──────────────────────────────────────────────
# 图表生成
# ──────────────────────────────────────────────

def generate_charts(pk_data, indices, all_stocks, sector_perf, stock_list):
    """生成多面板图表"""
    paths = {}
    today = datetime.now().strftime("%Y%m%d")

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    fig.patch.set_facecolor(BG)
    for ax in [ax1, ax2, ax3, ax4]:
        ax.set_facecolor(CARD)
        ax.tick_params(colors="white")
        ax.grid(True, alpha=0.15)

    # 1.1: 策略净值曲线
    pk_colors = ["#ef4444", "#3b82f6", "#eab308", "#22c55e", "#a78bfa"]
    for idx, d in enumerate(pk_data):
        cfg = STRATEGIES[d["id"]]
        nav = get_nav_history(get_strategy_db_path(cfg["id"]))
        if len(nav) >= 2:
            dates = [n["date"] for n in nav]
            vals = [n["total_assets"] for n in nav]
            ax1.plot(dates, vals, color=pk_colors[idx], linewidth=2,
                     label=f"{d['emoji']} {d['name']}")
    ax1.axhline(y=INITIAL_CAPITAL, color="#475569", linestyle=":", alpha=0.5)
    ax1.set_title("策略净值曲线", color="white", fontsize=13)
    ax1.legend(loc="upper left", facecolor=CARD, edgecolor="#334155",
               labelcolor="white", fontsize=7)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=25, fontsize=7)

    # 1.2: 板块热度
    if sector_perf:
        sectors_sorted = sorted(sector_perf.items(), key=lambda x: -x[1])
        names = [s[0] for s in sectors_sorted][:10]
        vals = [s[1] for s in sectors_sorted][:10]
        colors_bar = [GREEN if v >= 0 else RED for v in vals]
        ax2.barh(range(len(names)), vals, color=colors_bar, height=0.6)
        ax2.set_yticks(range(len(names)))
        ax2.set_yticklabels(names, fontsize=9, color="white")
        ax2.axvline(x=0, color="white", linewidth=0.5)
        ax2.set_title("板块热度 (平均涨跌幅%)", color="white", fontsize=13)
        ax2.invert_yaxis()

    # 1.3: 个股涨跌榜
    top10 = stock_list[:10]
    bot10 = stock_list[-10:][::-1]
    combined = top10 + [{"name": "...", "change_pct": 0}] + bot10
    names_comb = [s["name"][:4] for s in combined]
    vals_comb = [s["change_pct"] for s in combined]
    colors_comb = [GREEN if v >= 0 else RED for v in vals_comb]
    ax3.bar(range(len(names_comb)), vals_comb, color=colors_comb, width=0.6)
    ax3.axhline(y=0, color="white", linewidth=0.5)
    ax3.set_xticks(range(0, len(names_comb), 2))
    ax3.set_xticklabels(
        [names_comb[i] for i in range(0, len(names_comb), 2)],
        rotation=30, fontsize=7, color="white",
    )
    ax3.set_title("个股涨跌榜 (TOP10 + BOT10)", color="white", fontsize=13)

    # 1.4: 三大指数
    if indices:
        idx_names = list(indices.keys())
        idx_vals = [indices[n]["change_pct"] for n in idx_names]
        idx_colors = [GREEN if v >= 0 else RED for v in idx_vals]
        ax4.bar(idx_names, idx_vals, color=idx_colors, width=0.4)
        ax4.axhline(y=0, color="white", linewidth=0.5)
        ax4.set_title("三大指数", color="white", fontsize=13)
        for i, name in enumerate(idx_names):
            ax4.text(i, idx_vals[i] + (0.3 if idx_vals[i] >= 0 else -0.5),
                     f"{idx_vals[i]:+.2f}%", ha="center", color="white",
                     fontsize=10, fontweight="bold")

    plt.tight_layout(pad=3)
    path1 = os.path.join(REPORTS_DIR, f"research_charts_{today}.png")
    plt.savefig(path1, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    paths["main"] = path1

    return paths


def _img_b64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ──────────────────────────────────────────────
# HTML 构建
# ──────────────────────────────────────────────

def build_html(today, now, indices, sector_perf, stock_list, pk_data, chart_paths):
    """构建完整HTML研报"""
    main_img = _img_b64(chart_paths.get("main", ""))

    # 大盘概览
    idx_rows = ""
    if indices:
        for name, d in indices.items():
            c = GREEN if d["change_pct"] >= 0 else RED
            vol_str = f"{d['volume']/1e8:.1f}亿" if d.get("volume", 0) > 0 else "—"
            idx_rows += f"""
            <div class="grid-item">
                <div class="val" style="color:{c};">{d['change_pct']:+.2f}%</div>
                <div class="lbl">{name}</div>
                <div style="font-size:10px;color:{NEUTRAL};margin-top:2px;">{d['price']:.0f} | 量{vol_str}</div>
            </div>"""
    if not idx_rows:
        idx_rows = '<div class="grid-item"><div class="val" style="color:#9ca3af;">—</div><div class="lbl">非交易时段</div></div>'

    # 板块热度
    sector_rows = ""
    if sector_perf:
        sorted_sec = sorted(sector_perf.items(), key=lambda x: -x[1])
        for name, val in sorted_sec:
            c = GREEN if val >= 0 else RED
            sector_rows += f"""
            <tr>
                <td style="padding:5px 10px;border-bottom:1px solid #1f2937;">{name}</td>
                <td style="padding:5px 10px;border-bottom:1px solid #1f2937;text-align:right;color:{c};font-weight:bold;">{val:+.1f}%</td>
                <td style="padding:5px 10px;border-bottom:1px solid #1f2937;text-align:right;font-size:11px;color:{NEUTRAL};">{len(SECTOR_MAP[name])}只</td>
            </tr>"""

    # 股票池
    pool_rows = ""
    for name, code in STOCK_POOL.items():
        s = next((x for x in stock_list if x["code"] == code), None)
        if s:
            c = GREEN if s["change_pct"] >= 0 else RED
            pool_rows += f"""
            <tr>
                <td style="padding:3px 8px;font-size:11px;">{s['name']}</td>
                <td style="padding:3px 8px;font-size:10px;color:{NEUTRAL};">{s['code']}</td>
                <td style="padding:3px 8px;text-align:right;font-size:11px;color:{c};font-weight:bold;">{s['change_pct']:+.1f}%</td>
                <td style="padding:3px 8px;text-align:right;font-size:11px;">{s['close']:.2f}</td>
            </tr>"""
    if not pool_rows:
        pool_rows = '<tr><td colspan="4" style="padding:10px;text-align:center;color:#9ca3af;">等待行情数据</td></tr>'

    # 涨跌榜
    top5 = stock_list[:5]
    bot5 = stock_list[-5:]

    top_rows = ""
    for rank, s in enumerate(top5):
        c = GREEN if s["change_pct"] >= 0 else RED
        med = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"{rank+1}"
        top_rows += f"""
        <tr>
            <td style="padding:4px 8px;text-align:center;">{med}</td>
            <td style="padding:4px 8px;font-size:11px;">{s['name']}<br><span style="font-size:10px;color:{NEUTRAL};">{s['code']}</span></td>
            <td style="padding:4px 8px;text-align:right;font-size:11px;">{s['close']:.2f}</td>
            <td style="padding:4px 8px;text-align:right;color:{c};font-weight:bold;">{s['change_pct']:+.1f}%</td>
        </tr>"""

    bot_rows = ""
    for rank, s in enumerate(bot5):
        c = GREEN if s["change_pct"] >= 0 else RED
        bot_rows += f"""
        <tr>
            <td style="padding:4px 8px;text-align:center;">🔻</td>
            <td style="padding:4px 8px;font-size:11px;">{s['name']}<br><span style="font-size:10px;color:{NEUTRAL};">{s['code']}</span></td>
            <td style="padding:4px 8px;text-align:right;font-size:11px;">{s['close']:.2f}</td>
            <td style="padding:4px 8px;text-align:right;color:{c};font-weight:bold;">{s['change_pct']:+.1f}%</td>
        </tr>"""

    # 策略PK排名
    pk_rows = ""
    for rank, d in enumerate(pk_data):
        med = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][rank]
        tc = GREEN if d["cum_ret"] >= 0 else RED
        dpc = GREEN if d["daily_pnl"] >= 0 else RED
        pk_rows += f"""
        <tr>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;text-align:center;font-size:16px;">{med}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;"><strong>{d['emoji']} {d['name']}</strong></td>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;text-align:right;font-weight:bold;">{d['total']:,.0f}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;text-align:right;color:{tc};font-weight:bold;">{d['cum_ret']:+.2f}%</td>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;text-align:right;color:{dpc};">{d['daily_pnl']:+,.0f}</td>
            <td style="padding:8px 10px;border-bottom:1px solid #1f2937;text-align:right;">{d['n_pos']}只</td>
        </tr>"""

    # 策略持仓详情
    pk_detail = ""
    for d in pk_data:
        pos = d.get("positions", [])
        pos_html = ""
        if pos:
            for p in pos[:5]:
                pc = GREEN if p["pnl_pct"] >= 0 else RED
                pos_html += f"""
                <tr><td style="padding:3px 8px;font-size:10px;">{p['stock_name']}</td>
                <td style="padding:3px 8px;font-size:10px;text-align:right;">{p['shares']}股</td>
                <td style="padding:3px 8px;font-size:10px;text-align:right;color:{pc};">{p['pnl_pct']:+.1f}%</td></tr>"""
        else:
            pos_html = '<tr><td colspan="3" style="padding:6px;text-align:center;color:#9ca3af;font-size:10px;">空仓</td></tr>'

        today_str = datetime.now().strftime("%Y-%m-%d")
        cfg = STRATEGIES[d["id"]]
        trades_today = get_today_trades(get_strategy_db_path(cfg["id"]), today_str)
        trade_html = ""
        if trades_today:
            for t in trades_today[:10]:
                tc = GREEN if t["action"] == "买入" else RED
                act_icon = "🟢" if t["action"] == "买入" else "🔴"
                trade_html += f"""
                <tr><td style="padding:2px 6px;font-size:9px;color:{tc};font-weight:bold;">{act_icon} {t['action']}</td>
                <td style="padding:2px 6px;font-size:9px;">{t['stock_name']}</td>
                <td style="padding:2px 6px;font-size:9px;text-align:right;">{t['shares']}股</td>
                <td style="padding:2px 6px;font-size:9px;text-align:right;">¥{t['price']:.2f}</td>
                <td style="padding:2px 6px;font-size:9px;color:{NEUTRAL};">{t['reason'][:12]}</td></tr>"""
        else:
            trade_html = '<tr><td colspan="5" style="padding:4px;text-align:center;color:#9ca3af;font-size:9px;">今日无调仓</td></tr>'

        pk_detail += f"""
        <div class="card" style="flex:1;min-width:200px;">
            <div style="font-size:13px;color:{BLUE};font-weight:600;margin-bottom:6px;">{d['emoji']} {d['name']}</div>
            <div style="text-align:center;margin-bottom:6px;">
                <span style="font-size:18px;font-weight:bold;">{d['total']:,.0f}</span>
                <span style="font-size:11px;color:{GREEN if d['cum_ret']>=0 else RED};">({d['cum_ret']:+.1f}%)</span>
            </div>
            <div style="font-size:10px;color:{NEUTRAL};margin:4px 0;">📋 持仓</div>
            <table>{pos_html}</table>
            <div style="font-size:10px;color:{NEUTRAL};margin:6px 0 4px;">🔄 今日调仓</div>
            <table>{trade_html}</table>
        </div>"""

    # 风险提示
    warnings = []
    for s in stock_list:
        if s["change_pct"] > 8:
            warnings.append(f"📈 {s['name']}({s['code']}) 单日暴涨 {s['change_pct']:+.1f}%，注意追高风险")
        elif s["change_pct"] < -6:
            warnings.append(f"📉 {s['name']}({s['code']}) 单日暴跌 {s['change_pct']:+.1f}%，关注是否触发止损")
    if not warnings:
        warnings.append("✅ 今日无异常波动，市场运行平稳")
    warn_html = "".join(
        f'<div style="padding:6px 0;border-bottom:1px solid #1f2937;font-size:12px;">{w}</div>'
        for w in warnings
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投资研报 {today}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif; background:{BG}; color:#e2e8f0; padding:16px; }}
.container {{ max-width:960px; margin:0 auto; }}
h1 {{ font-size:20px; color:#f1f5f9; }}
h2 {{ font-size:15px; color:{BLUE}; margin:14px 0 8px; padding-bottom:6px; border-bottom:1px solid #1f2937; }}
.date {{ font-size:12px; color:{NEUTRAL}; margin-bottom:14px; }}
.card {{ background:{CARD}; border-radius:10px; padding:12px; margin-bottom:10px; }}
.card-title {{ font-size:13px; color:{BLUE}; font-weight:600; margin-bottom:8px; }}
.card-row {{ display:flex; gap:10px; flex-wrap:wrap; }}
.grid-2 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }}
.grid-item {{ background:{BG}; border-radius:8px; padding:10px; text-align:center; }}
.grid-item .val {{ font-size:20px; font-weight:bold; }}
.grid-item .lbl {{ font-size:10px; color:#64748b; margin-top:3px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th {{ text-align:left; color:#64748b; font-weight:500; font-size:10px; padding:5px 8px; border-bottom:2px solid #1f2937; }}
.chart img {{ width:100%; display:block; border-radius:8px; }}
.footer {{ text-align:center; color:#475569; font-size:10px; margin-top:16px; padding:12px 0; }}
.tag {{ display:inline-block; padding:2px 6px; border-radius:3px; font-size:10px; font-weight:bold; }}
</style>
</head>
<body><div class="container">

<h1>🏆 A股量化工具箱 · 投资研报</h1>
<div class="date">{today} {now} | 股票池 {len(STOCK_POOL)}只 | 初始资金 ¥1,000,000 | 5策略PK</div>

<!-- 大盘 -->
<h2>📊 大盘概览</h2>
<div class="grid-2">{idx_rows}</div>

<!-- 图表 -->
<div class="card"><div class="chart"><img src="data:image/png;base64,{main_img}"></div></div>

<!-- 板块 + 策略 -->
<div class="card-row">
    <div class="card" style="flex:1;">
        <div class="card-title">🔥 板块热度</div>
        <table>{sector_rows if sector_rows else '<tr><td style="padding:10px;color:#9ca3af;">等待数据</td></tr>'}</table>
    </div>
    <div class="card" style="flex:2;">
        <div class="card-title">🏆 策略PK排名</div>
        <table>
            <tr><th style="width:36px;text-align:center;">排</th><th>策略</th><th style="text-align:right;">总资产</th><th style="text-align:right;">累计</th><th style="text-align:right;">当日</th><th style="text-align:right;">仓</th></tr>
            {pk_rows}
        </table>
    </div>
</div>

<!-- 策略持仓 -->
<h2>📦 策略持仓明细</h2>
<div class="card-row">{pk_detail}</div>

<!-- 个股涨跌榜 -->
<div class="card-row">
    <div class="card" style="flex:1;">
        <div class="card-title">🔥 今日涨幅TOP5</div>
        <table>{top_rows}</table>
    </div>
    <div class="card" style="flex:1;">
        <div class="card-title">📉 今日跌幅TOP5</div>
        <table>{bot_rows}</table>
    </div>
</div>

<!-- 完整股票池 -->
<h2>📋 全部股票池 ({len(STOCK_POOL)}只 · {len(SECTOR_MAP)}个板块)</h2>
<div class="card" style="max-height:500px;overflow-y:auto;">
    <table>
        <tr><th>股票</th><th>代码</th><th style="text-align:right;">涨跌幅</th><th style="text-align:right;">现价</th></tr>
        {pool_rows}
    </table>
</div>

<!-- 风险提示 -->
<h2>⚠️ 风险提示</h2>
<div class="card">{warn_html}</div>

<!-- 策略说明 -->
<div class="card" style="background:{BLUE}10; border:1px solid {BLUE}22;">
    <div class="card-title">📖 策略说明</div>
    <table>
        <tr><td style="padding:4px 8px;">🔥 放量上攻</td><td style="font-size:11px;color:#94a3b8;">成交量>1.5倍均量+上涨 → 追量价爆发，持仓5只</td></tr>
        <tr><td style="padding:4px 8px;">📊 倍量抄底逃顶</td><td style="font-size:11px;color:#94a3b8;">左倍量(低位放量)买入，右倍量(高位放量滞涨)卖出</td></tr>
        <tr><td style="padding:4px 8px;">📅 等权全池</td><td style="font-size:11px;color:#94a3b8;">全仓等权配置209只，被动持有，再平衡</td></tr>
        <tr><td style="padding:4px 8px;">🔄 反转猎人</td><td style="font-size:11px;color:#94a3b8;">买超跌股：5日跌>3% + 近60日低点 + 缩量</td></tr>
        <tr><td style="padding:4px 8px;">🤖 AI量化 (Ridge ML)</td><td style="font-size:11px;color:#94a3b8;">Ridge回归预测次日收益，30+因子特征工程，TOP5轮动</td></tr>
    </table>
</div>

<div class="footer">A股量化工具箱 · {today} {now}</div>

</div></body></html>"""

    return html


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def generate_full_report():
    """生成完整投资研报"""
    today = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now().strftime("%H:%M")

    print("📊 获取大盘数据...")
    indices = fetch_market_indices()

    print("📈 获取股票池数据...")
    all_stocks = fetch_all_stocks_data()

    # 板块表现
    sector_perf = {}
    for sec_name, sec_codes in SECTOR_MAP.items():
        rets = []
        for c in sec_codes:
            s = all_stocks.get(c, {})
            if s and s.get("change_pct") is not None:
                rets.append(s["change_pct"])
        if rets:
            sector_perf[sec_name] = round(sum(rets) / len(rets), 2)

    # 个股排名
    stock_list = []
    for code, s in all_stocks.items():
        stock_list.append({
            "code": code,
            "name": s.get("name", code),
            "close": s.get("close", 0),
            "change_pct": s.get("change_pct", 0),
            "volume": s.get("volume", 0),
            "amount": s.get("amount", 0),
            "high": s.get("high", 0),
            "low": s.get("low", 0),
        })
    stock_list.sort(key=lambda x: -x["change_pct"])

    # 策略PK数据
    print("🏆 策略PK数据...")
    pk_data = []
    for sid, cfg in STRATEGIES.items():
        acct = get_account(get_strategy_db_path(sid))
        positions = get_positions(get_strategy_db_path(sid))
        if acct:
            pk_data.append({
                "id": sid,
                "name": cfg["name"],
                "emoji": cfg["emoji"],
                "total": acct["total_assets"],
                "cash": acct["cash"],
                "cum_ret": acct.get("cumulative_return", 0),
                "daily_pnl": acct.get("daily_pnl", 0),
                "n_pos": len(positions),
                "positions": positions,
            })
    pk_data.sort(key=lambda x: -x["total"])

    # 图表
    print("📉 生成图表...")
    chart_paths = generate_charts(pk_data, indices, all_stocks, sector_perf, stock_list)

    # HTML
    html = build_html(today, now, indices, sector_perf, stock_list, pk_data, chart_paths)

    html_path = os.path.join(REPORTS_DIR, f"research_{today}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 研报生成: {html_path}")
    return html_path, chart_paths


def main():
    generate_full_report()


if __name__ == "__main__":
    main()
