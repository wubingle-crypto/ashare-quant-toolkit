<div align="center">

# 📈 A股量化工具箱 · A-Share Quant Toolkit

**多策略每日竞赛系统 — 5大量化策略每日同台竞技**

</div>

[English](#english) | [中文](#中文)

---

## 🇨🇳 中文

### 📖 项目简介

**A股量化工具箱** 是一个开源的A股量化交易研究与竞赛系统。它每天自动运行5个不同的量化策略（放量上攻、倍量抄底逃顶、等权全池、反转猎人、AI量化Ridge ML），每个策略拥有独立的100万模拟资金账户，在同一起跑线上每日PK。

系统自动获取实时行情 ✓ 执行交易 ✓ 记录净值 ✓ 生成HTML投资研报 ✓

> 🚀 **从零到一：5大策略每日 PK，百万模拟资金同台竞技，一键生成完整投资研报。**
> **适合人群：A股量化入门者、策略研究员、对 AI 选股感兴趣的同学。**
> **开源 · 纯 Python · 中国网络友好 · 即装即用**

### ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 🏆 **5策略竞赛** | 放量上攻、倍量抄底逃顶、等权全池、反转猎人、AI量化 (Ridge ML) |
| 🚀 **每日自动运行** | 一套命令完成行情获取 → 信号生成 → 交易执行 → 净值结算 → 研报输出 |
| 📊 **完整投资研报** | 自动生成包含大盘分析、板块热度、个股扫描、策略PK排名的HTML报告 |
| 🔌 **双数据源** | 腾讯实时行情 `qt.gtimg.cn`（盘中）+ `akshare` 历史数据（盘后分析） |
| 🤖 **AI量化策略** | 基于 Ridge 回归的机器学习选股，30+技术面特征 |
| 🗄️ **独立数据库** | 每个策略独立 SQLite 数据库文件，便于分析 |
| 🐍 **纯 Python** | 依赖简洁，pip install 即可使用 |
| 🌐 **中国网络友好** | 所有数据源在中国大陆网络均可正常访问 |

### 🎮 一分钟 Demo — 2行代码获取实时行情

```python
from ashare_quant_toolkit.data_fetcher import fetch_tencent_realtime_as_df

df = fetch_tencent_realtime_as_df(["000001", "000333", "000858", "002594", "600519"])
print(df[["name", "close", "change_pct"]])
```

运行 `python demo.py` 即可看到效果，无需任何 API Key！

### 🚀 快速开始

```bash
# 1. 安装
pip install -r requirements.txt

# 2. 运行所有策略
python -m ashare_quant_toolkit.competition

# 3. 运行单个策略
python -m ashare_quant_toolkit.strategies.surge
python -m ashare_quant_toolkit.strategies.double_vol
python -m ashare_quant_toolkit.strategies.equal
python -m ashare_quant_toolkit.strategies.reversal
python -m ashare_quant_toolkit.strategies.ai_quant

# 4. 生成研报（依赖策略竞赛数据）
python -m ashare_quant_toolkit.reporter
```

### 🏗️ 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| 数据处理 | pandas, numpy |
| 机器学习 | scikit-learn (Ridge Regression) |
| 行情数据 | Tencent qt.gtimg.cn (实时), akshare (历史) |
| 数据存储 | SQLite (每策略独立数据库) |
| 可视化 | matplotlib |
| 报告生成 | HTML + Base64 内嵌图表 |

### 📁 项目结构

```
ashare-quant-toolkit/
├── pyproject.toml          # 项目配置
├── requirements.txt        # 依赖清单
├── LICENSE                 # MIT 许可证
├── README.md               # 本文档
└── src/
    └── ashare_quant_toolkit/
        ├── __init__.py
        ├── config.py           # 配置（209只股票池、交易参数、板块映射）
        ├── data_fetcher.py     # 数据获取（腾讯实时行情 + akshare历史数据）
        ├── db.py               # 数据库层（账户、持仓、交易、净值）
        ├── engine.py           # 交易引擎（买入/卖出执行、日终结算）
        ├── indicators.py       # 技术指标计算
        ├── competition.py      # 竞赛运行入口
        ├── reporter.py         # 投资研报生成器
        └── strategies/
            ├── __init__.py
            ├── base.py         # 策略基类
            ├── surge.py        # 策略1: 放量上攻 🔥
            ├── double_vol.py   # 策略2: 倍量抄底逃顶 📊
            ├── equal.py        # 策略3: 等权全池 📅
            ├── reversal.py     # 策略4: 反转猎人 🔄
            └── ai_quant.py     # 策略5: AI量化 (Ridge ML) 🤖
```

### 📋 支持的股票池

初始股票池包含 **209只A股**，覆盖12大行业板块：
- AI算力、半导体、新能源、机器人、消费电子、医药
- 白酒消费、金融、低空航天、有色电力、地产基建、交运物流

代码自动过滤科创板(688xxx)和北证(8xxxxx)。

### ⚠️ 免责声明

本项目仅供学习和研究量化交易策略。**不构成任何投资建议**。股市有风险，投资需谨慎。过往表现不代表未来收益。

---

## 🇬🇧 English

### 📖 Introduction

**A-Share Quant Toolkit** is an open-source quantitative trading research and competition system for China A-Share market. It runs 5 different quantitative strategies daily, each with an independent ¥1,000,000 simulated capital account, competing against each other on a level playing field.

Real-time market data ✓ Trade execution ✓ NAV recording ✓ HTML research report ✓

### ✨ Features

| Feature | Description |
|---------|-------------|
| 🏆 **5-Strategy Competition** | Surge, Double Volume, Equal Weight, Reversal Hunter, AI Quant (Ridge ML) |
| 🚀 **Daily Auto-Run** | One command: fetch data → generate signals → execute trades → settlement → report |
| 📊 **Full Research Report** | Auto-generated HTML report with market analysis, sector heatmap, strategy PK |
| 🔌 **Dual Data Sources** | Tencent real-time quotes `qt.gtimg.cn` + `akshare` historical data |
| 🤖 **AI Quant Strategy** | Ridge Regression ML stock selection with 30+ technical features |
| 🗄️ **Independent DB** | Each strategy has its own SQLite database for easy analysis |
| 🐍 **Pure Python** | Minimal dependencies, pip install & go |
| 🌐 **China-Friendly** | All data sources accessible within mainland China |

### 🚀 Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Run all strategies
python -m ashare_quant_toolkit.competition

# 3. Run single strategy
python -m ashare_quant_toolkit.strategies.surge
python -m ashare_quant_toolkit.strategies.double_vol
python -m ashare_quant_toolkit.strategies.equal
python -m ashare_quant_toolkit.strategies.reversal
python -m ashare_quant_toolkit.strategies.ai_quant

# 4. Generate report
python -m ashare_quant_toolkit.reporter
```

### 🏗️ Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| Data Processing | pandas, numpy |
| Machine Learning | scikit-learn (Ridge Regression) |
| Market Data | Tencent qt.gtimg.cn (real-time), akshare (historical) |
| Storage | SQLite (per-strategy database) |
| Visualization | matplotlib |
| Reports | HTML with base64-embedded charts |

### ⚠️ Disclaimer

This project is for **educational and research purposes only**. It does **NOT constitute investment advice**. Past performance does not guarantee future results. Trade at your own risk.

---

## 💖 赞助 / Support

| 方式 | 地址 |
|------|------|
| **BSC (BEP-20)** | `0x19979a2498867a1bC0F823Fd309B05eEe8Bc5624` |
| **ETH** | 同上地址 |
