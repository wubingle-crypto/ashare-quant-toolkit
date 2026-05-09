"""
策略5: AI量化 (Ridge ML)
========================
核心逻辑：Ridge回归预测次日收益，TOP5持仓
30+技术面特征，每21天重新训练模型
"""

import time
from datetime import datetime

import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge

from ashare_quant_toolkit.config import VALIDATED_STOCK_POOL, CODE_TO_NAME
from ashare_quant_toolkit.data_fetcher import get_stock_history
from ashare_quant_toolkit.indicators import engineer_ml_features

# 模型缓存（进程级）
_MODEL_CACHE = {}
_MODEL_LAST_TRAIN = {}


def generate_signals(prices_df, positions, account, config):
    """
    AI量化信号生成

    逻辑：
    1. 获取1.5年历史数据
    2. 工程化30+技术特征
    3. Ridge回归训练/预测
    4. 预测收益TOP5买入，不在TOP5的卖出
    """
    signals = {"buy": [], "sell": []}
    max_pos = config["max_positions"]

    if prices_df is None or prices_df.empty:
        return signals

    codes = list(VALIDATED_STOCK_POOL.values())
    codes = [c for c in codes if not c.startswith("_")]

    # 获取ML训练数据
    df_ml = _fetch_ml_data(codes)
    if df_ml is None or len(df_ml) < 50:
        return signals

    # 特征工程
    df_feat = engineer_ml_features(df_ml)
    if df_feat is None or len(df_feat) < 50:
        return signals

    # 取每只股票最新一行
    latest = df_feat.groupby("code").last().reset_index()
    feature_cols = [
        c for c in latest.columns
        if c not in ("code", "name", "date", "target", "close", "volume", "open", "high", "low")
    ]

    # 训练/加载模型
    model_id = "ai_quant_ridge"
    should_retrain = (
        _MODEL_LAST_TRAIN.get(model_id) is None
        or (datetime.now() - _MODEL_LAST_TRAIN[model_id]).days >= 21
    )

    if should_retrain or model_id not in _MODEL_CACHE:
        train_data = df_feat.dropna(subset=["target"]).copy()
        if len(train_data) > 500:
            X = train_data[feature_cols].values
            y = train_data["target"].values
            valid = ~np.isnan(y)
            X = X[valid]
            y = y[valid]
            model = Ridge(alpha=1.0)
            model.fit(X, y)
            _MODEL_CACHE[model_id] = (model, feature_cols)
            _MODEL_LAST_TRAIN[model_id] = datetime.now()

    if model_id in _MODEL_CACHE:
        model, feat_cols = _MODEL_CACHE[model_id]
        valid_feats = [c for c in feat_cols if c in latest.columns]
        if len(valid_feats) < 10:
            return signals

        X_pred = latest[valid_feats].values
        try:
            preds = model.predict(X_pred)
        except Exception:
            return signals

        latest = latest.copy()
        latest["pred"] = preds

        top_n = min(max_pos, len(latest))
        top = latest.nlargest(top_n, "pred")
        target_codes = set(top["code"].values)

        # 卖出不在预测TOP的持仓
        for pos in positions:
            if pos["stock_code"] not in target_codes:
                cur = pos["current_price"]
                if cur > 0:
                    signals["sell"].append(
                        (pos["stock_code"], pos["stock_name"], cur, pos["shares"], "ml_rotate")
                    )

        # 买入预测TOP
        cash = account["cash"]
        remaining = max_pos - len(positions) + len(signals["sell"])
        if remaining <= 0:
            return signals
        cash_per = cash / remaining

        for _, row in top.iterrows():
            code = row["code"]
            if code in [p["stock_code"] for p in positions]:
                continue
            if len(signals["buy"]) >= remaining:
                break
            price = row["close"]
            if price <= 0:
                continue
            name = CODE_TO_NAME.get(code, row.get("name", code))
            sh = int(cash_per / price / 100) * 100
            if sh >= 100:
                signals["buy"].append((code, name, price, sh, f"ml_pred:{row['pred']:.2f}"))

    return signals


def _fetch_ml_data(codes):
    """获取1.5年历史数据用于ML训练"""
    all_frames = []
    today_str = datetime.now().strftime("%Y%m%d")

    for code in codes:
        try:
            df = get_stock_history(code, start_date="20240101", end_date=today_str)
            if df is not None and len(df) >= 60:
                df["code"] = code
                all_frames.append(df)
            time.sleep(0.08)
        except Exception:
            pass

    if not all_frames:
        return None
    return pd.concat(all_frames, ignore_index=True)


def run():
    """独立运行此策略"""
    from ashare_quant_toolkit.engine import run_strategy
    result = run_strategy("ai_quant", generate_signals)
    st = result.get("settlement", {})
    print(f"🤖 AI量化 (Ridge ML): ¥{st.get('total_assets', 0):,.0f} | "
          f"{st.get('cumulative_return', 0):+.2f}% | "
          f"持仓{len(result.get('positions', []))}只")
    return result


if __name__ == "__main__":
    run()
