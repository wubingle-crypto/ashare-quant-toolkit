"""
技术指标计算 — 用于 AI量化策略的特征工程
========================================
"""

import pandas as pd
import numpy as np


def engineer_ml_features(df):
    """
    从历史日线数据中工程化 30+ 机器学习特征

    Parameters
    ----------
    df : pd.DataFrame
        必须包含列: code, close, volume, high, low

    Returns
    -------
    pd.DataFrame or None
        包含所有特征 + target（次日收益）
    """
    result_frames = []

    for code in df["code"].unique():
        cdf = df[df["code"] == code].copy().sort_values("date").reset_index(drop=True)
        c = cdf["close"].values.astype(float)
        v = cdf["volume"].values.astype(float)
        h = cdf["high"].values.astype(float)
        lo = cdf["low"].values.astype(float)
        n = len(c)

        if n < 60:
            continue

        # 收益率
        for w in [1, 3, 5, 10, 20, 60]:
            cdf[f"ret_{w}d"] = pd.Series(c).pct_change(w) * 100

        # 均线比
        for w in [5, 10, 20, 60]:
            ma = pd.Series(c).rolling(w).mean().values
            cdf[f"ma_{w}"] = ma
            cdf[f"price_div_ma{w}"] = c / ma

        cdf["ma5_div_ma20"] = cdf["ma_5"] / cdf["ma_20"].replace(0, np.nan)
        cdf["ma10_div_ma60"] = cdf["ma_10"] / cdf["ma_60"].replace(0, np.nan)

        # 波动率 & 量比
        for w in [5, 10, 20]:
            cdf[f"volatility_{w}d"] = pd.Series(c).pct_change().rolling(w).std() * 100
            mv = pd.Series(v).rolling(w).mean()
            cdf[f"vol_ratio_{w}d"] = v / mv.replace(0, np.nan)

        cdf["vol_trend"] = cdf["vol_ratio_5d"] / cdf["vol_ratio_20d"].replace(0, np.nan)

        # RSI
        for w in [5, 14]:
            delta = pd.Series(c).diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_g = gain.rolling(w).mean()
            avg_l = loss.rolling(w).mean().replace(0, 0.001)
            rs = avg_g / avg_l
            cdf[f"rsi_{w}"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = pd.Series(c).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(c).ewm(span=26, adjust=False).mean().values
        dif = ema12 - ema26
        dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values
        cdf["macd_hist"] = (dif - dea) * 2
        cdf["macd_bull"] = (dif > dea).astype(int)
        cdf["macd_divergence"] = (dif - dea) / (c + 0.001) * 100

        # 布林带位置
        ma20_b = pd.Series(c).rolling(20).mean().values
        std20_b = pd.Series(c).rolling(20).std().values
        upper = ma20_b + 2 * std20_b
        lower = ma20_b - 2 * std20_b
        cdf["bb_position"] = (c - lower) / (upper - lower + 0.001)

        # 距高低点距离
        cdf["dist_20d_high"] = (c - pd.Series(h).rolling(20).max()) / \
                                (pd.Series(h).rolling(20).max() + 0.001) * 100
        cdf["dist_20d_low"] = (c - pd.Series(lo).rolling(20).min()) / \
                               (pd.Series(lo).rolling(20).min() + 0.001) * 100
        cdf["dist_60d_high"] = (c - pd.Series(h).rolling(60).max()) / \
                                (pd.Series(h).rolling(60).max() + 0.001) * 100
        cdf["dist_60d_low"] = (c - pd.Series(lo).rolling(60).min()) / \
                               (pd.Series(lo).rolling(60).min() + 0.001) * 100

        # 目标值：次日收益率
        cdf["target"] = pd.Series(c).pct_change().shift(-1) * 100
        cdf["close"] = c
        cdf["volume"] = v
        cdf["high"] = h
        cdf["low"] = lo

        result_frames.append(cdf)

    if not result_frames:
        return None

    combined = pd.concat(result_frames, ignore_index=True)
    combined = combined.fillna(0)
    combined = combined.dropna(subset=["target"])
    return combined
