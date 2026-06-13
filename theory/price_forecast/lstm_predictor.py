""" (4) LSTM 时序预测：支持 ts-only 与 fusion 两种已训练模型。"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from theory.price_forecast.data_loader import feature_columns, load_merged_symbol
from theory.price_forecast.tf_backend import get_tensorflow
from theory.shared.paths import (
    ALL_TRAIN_MODES,
    FORECAST_HORIZON,
    MODEL_TS_ONLY,
    SEQ_LENGTH,
    is_fusion_mode,
    model_paths,
)


def load_price_data() -> pd.DataFrame:
    from theory.shared.paths import CLEANED_CSV

    if not CLEANED_CSV.exists():
        raise FileNotFoundError(f"未找到 {CLEANED_CSV}，请先运行 python run.py setup-data")
    return pd.read_csv(CLEANED_CSV, parse_dates=["Date"])


def _roll_forecast(
    scaled: np.ndarray,
    model,
    scaler,
    n_features: int,
    horizon: int,
    last_close: float,
    vol: float,
    last_date,
) -> dict:
    input_seq = scaled[-SEQ_LENGTH:].copy()
    predictions, confidence_scores = [], []

    for _ in range(horizon):
        pred_scaled = model.predict(
            np.reshape(input_seq, (1, SEQ_LENGTH, n_features)), verbose=0
        )
        pred_close_scaled = float(pred_scaled[0][0])
        inv_row = input_seq[-1].copy()
        inv_row[0] = pred_close_scaled
        pred_price = float(scaler.inverse_transform([inv_row])[0][0])

        predictions.append(pred_price)
        window = predictions[-5:] if len(predictions) >= 5 else predictions
        confidence_scores.append(max(0.0, min(1.0, 1 - (np.std(window) / (vol + 1e-6)))))

        next_row = input_seq[-1].copy()
        next_row[0] = pred_close_scaled
        input_seq = np.vstack([input_seq[1:], next_row])

    if hasattr(last_date, "date"):
        last_date = last_date.date()
    dates = [
        (last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d")
        for i in range(horizon)
    ]
    daily, prev = [], last_close
    for d, pred, conf in zip(dates, predictions, confidence_scores):
        daily.append({
            "date": d,
            "predicted_close": round(pred, 2),
            "trend": "UP" if pred > prev else "DOWN",
            "percent_change": f"{((pred - prev) / prev * 100) if prev else 0:+.2f}%",
            "confidence": round(conf, 4),
        })
        prev = pred

    return {
        "last_close": last_close,
        "last_date": str(last_date),
        "avg_lstm_price": round(float(np.mean(predictions)), 2),
        "avg_lstm_confidence": round(float(np.mean(confidence_scores)), 4),
        "forecast_7d": daily,
        "predicted_prices": predictions,
    }


def forecast_from_dataframe(
    df: pd.DataFrame,
    mode: str,
    model,
    scaler,
    horizon: int = FORECAST_HORIZON,
    live_sentiment: Optional[float] = None,
) -> dict:
    """基于截断历史 DataFrame 做滚动预测（回测用）。"""
    cols = feature_columns(mode)
    work = df[cols].astype(float).copy()
    if is_fusion_mode(mode) and live_sentiment is not None:
        work.iloc[-1, work.columns.get_loc("signed_score")] = float(live_sentiment)

    scaled = scaler.transform(work.values)
    last_close = float(df["Close"].iloc[-1])
    last_date = df["Date"].iloc[-1]
    vol = df["Close"].rolling(SEQ_LENGTH).std().iloc[-1]
    if pd.isna(vol) or vol == 0:
        vol = float(df["Close"].std())

    out = _roll_forecast(
        scaled, model, scaler, scaled.shape[1], horizon, last_close, vol, last_date
    )
    return out


def forecast_stock(
    symbol: str,
    mode: str = MODEL_TS_ONLY,
    live_sentiment: Optional[float] = None,
    history_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    mode: ts-only | fusion-bert | fusion
    live_sentiment: 推理时用当日新闻情感分数覆盖最后一天情感（仅 fusion 类模式）
    history_df: 若提供则在该截断历史上预测（回测）
    """
    symbol = symbol.strip()
    if mode not in ALL_TRAIN_MODES:
        raise ValueError(f"未知 mode: {mode}")

    df = history_df if history_df is not None else load_merged_symbol(symbol, mode)
    if len(df) < SEQ_LENGTH:
        raise ValueError(f"{symbol} 历史数据不足 {SEQ_LENGTH} 天")

    model_path, scaler_path = model_paths(symbol, mode)
    if not (model_path.exists() and scaler_path.exists()):
        raise FileNotFoundError(
            f"未找到 [{mode}] 模型，请先: python run.py train --mode {mode} --symbols {symbol}"
        )

    tf = get_tensorflow()
    model = tf.keras.models.load_model(model_path)
    scaler = joblib.load(scaler_path)

    out = forecast_from_dataframe(df, mode, model, scaler, live_sentiment=live_sentiment)
    out["symbol"] = symbol
    out["mode"] = mode
    return out
