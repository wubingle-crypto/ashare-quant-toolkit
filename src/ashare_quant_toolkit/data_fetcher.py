"""
股票数据获取模块
================
双数据源: 腾讯实时行情 (qt.gtimg.cn) + akshare 历史数据 (stock_zh_a_hist_tx)
"""

import subprocess
import time
from datetime import datetime, timedelta

import pandas as pd
import numpy as np


def get_market_prefix(code: str) -> str:
    """根据股票代码获取腾讯API前缀"""
    if code.startswith("6") or code.startswith("68"):
        return "sh"
    elif code.startswith("0") or code.startswith("3"):
        return "sz"
    return "sh"


def fetch_tencent_realtime(codes):
    """
    通过腾讯实时行情 API (qt.gtimg.cn) 获取最新行情

    Parameters
    ----------
    codes : list of str
        股票代码列表

    Returns
    -------
    dict
        {code: {name, close, prev_close, open, volume, high, low, change_pct, amount}}
    """
    if isinstance(codes, str):
        codes = [codes]

    symbols = []
    code_prefix_map = {}
    for code in codes:
        prefix = get_market_prefix(code)
        symbol = f"{prefix}{code}"
        symbols.append(symbol)
        code_prefix_map[symbol] = code

    url = f"http://qt.gtimg.cn/q={','.join(symbols)}"

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", url],
            capture_output=True, timeout=15
        )
        raw_text = result.stdout.decode("gbk", errors="replace")
        return _parse_tencent_realtime(raw_text)
    except Exception as e:
        print(f"腾讯行情获取失败: {e}")
        return {}


def _parse_tencent_realtime(raw_text):
    """解析腾讯实时行情返回的文本"""
    result = {}
    lines = raw_text.strip().split("\n")

    for line in lines:
        if "=" not in line:
            continue
        value = line.split("=", 1)[1].strip().strip('"').strip("'")
        parts = value.split("~")

        if len(parts) < 40:
            continue

        code = parts[2]
        try:
            current = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else 0

            result[code] = {
                "name": parts[1],
                "code": code,
                "close": current,
                "prev_close": prev_close,
                "open": float(parts[5]) if parts[5] else 0,
                "volume": int(float(parts[6])) if parts[6] else 0,
                "high": float(parts[33]) if parts[33] else current,
                "low": float(parts[34]) if parts[34] else current,
                "change_pct": float(parts[32]) if parts[32] else 0,
                "amount": float(parts[37]) if len(parts) > 37 and parts[37] else 0,
            }
        except (ValueError, IndexError):
            continue

    return result


def fetch_tencent_realtime_as_df(codes):
    """
    获取实时行情并返回 DataFrame

    Parameters
    ----------
    codes : list of str
        股票代码列表

    Returns
    -------
    pd.DataFrame
        包含 code, name, close, volume, change_pct 等字段
    """
    data = fetch_tencent_realtime(codes)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(list(data.values()))


def get_market_index():
    """获取三大指数（上证指数、沪深300、中证500）"""
    symbols = ["sh000001", "sh000300", "sh000905"]
    url = f"http://qt.gtimg.cn/q={','.join(symbols)}"

    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", url],
            capture_output=True, timeout=15
        )
        raw_text = result.stdout.decode("gbk", errors="replace")
        data = _parse_tencent_realtime(raw_text)

        name_map = {
            "000001": "上证指数",
            "000300": "沪深300",
            "000905": "中证500",
        }

        indices = {}
        for code, name in name_map.items():
            if code in data:
                indices[name] = {
                    "close": data[code]["close"],
                    "change_pct": data[code]["change_pct"],
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }
        return indices
    except Exception as e:
        print(f"获取大盘数据失败: {e}")
        return {}


def get_stock_history(code, start_date=None, end_date=None, adjust="qfq"):
    """
    使用 akshare 获取单只股票历史行情

    Parameters
    ----------
    code : str
        股票代码（纯数字，如 '000001'）
    start_date : str, optional
        开始日期 YYYYMMDD 或 YYYY-MM-DD
    end_date : str, optional
        结束日期
    adjust : str
        复权类型: 'qfq' 前复权, 'hfq' 后复权, '' 不复权

    Returns
    -------
    pd.DataFrame or None
        包含 date, open, close, high, low, volume（成交额）, change_pct 等字段
        注意：akshare 返回的 amount 字段已被重命名为 volume
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")

    # 统一格式
    start_date = str(start_date).replace("-", "")
    end_date = str(end_date).replace("-", "")

    try:
        import akshare as ak

        prefix = get_market_prefix(code)
        full_symbol = f"{prefix}{code}"

        df = ak.stock_zh_a_hist_tx(
            symbol=full_symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )

        if df is not None and not df.empty:
            # akshare Tencent 数据源返回的 'amount' 是成交额，重命名为 volume
            df = df.rename(columns={"amount": "volume"})
            # 添加代码列
            df["code"] = code
            # 计算涨跌幅
            df["change_pct"] = df["close"].pct_change() * 100
            return df
    except Exception as e:
        print(f"获取 {code} 历史数据失败: {e}")

    return None


def get_multi_stock_history(codes, start_date=None, end_date=None, delay=0.15):
    """
    批量获取多只股票历史数据

    Parameters
    ----------
    codes : list of str
    start_date, end_date : str, optional
    delay : float
        请求间隔（秒），避免被限速

    Returns
    -------
    pd.DataFrame
        合并后的数据，包含 code 列
    """
    all_frames = []
    for code in codes:
        df = get_stock_history(code, start_date, end_date)
        if df is not None and len(df) > 0:
            all_frames.append(df)
        time.sleep(delay)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)
