"""训练/预测用价量 + 情感对齐数据。"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from theory.shared.config import Settings
from theory.shared.paths import (
    CLEANED_CSV,
    DEFAULT_TEST_START,
    DEFAULT_TRAIN_END,
    MODEL_FUSION,
    MODEL_FUSION_BERT,
    MODEL_TS_ONLY,
    SEQ_LENGTH,
    is_fusion_mode,
    sentiment_csv_path,
)


def load_merged_symbol(symbol: str, mode: str) -> pd.DataFrame:
    if not CLEANED_CSV.exists():
        raise FileNotFoundError(f"缺少 {CLEANED_CSV}，请先 python run.py setup-data")

    price = pd.read_csv(CLEANED_CSV, parse_dates=["Date"])
    price = price[price["Symbol"] == symbol.strip()].sort_values("Date").copy()
    if price.empty:
        raise ValueError(f"数据集中无股票: {symbol}")

    if is_fusion_mode(mode):
        sent_csv = sentiment_csv_path(mode)
        if not sent_csv.exists():
            variant = "bert" if mode == MODEL_FUSION_BERT else "finbert"
            raise FileNotFoundError(
                f"融合训练需 {sent_csv}，请先: python run.py build-sentiment --variant {variant}"
            )
        sent = pd.read_csv(sent_csv, parse_dates=["Date"])
        sent = sent[sent["Symbol"] == symbol.strip()][
            ["Date", "signed_score", "positive", "negative"]
        ]
        merged = price.merge(sent, on="Date", how="left")
        merged["signed_score"] = merged["signed_score"].fillna(0.0)
        merged["positive"] = merged["positive"].fillna(0.0)
        merged["negative"] = merged["negative"].fillna(0.0)
        return merged

    return price


def split_train_test(
    df: pd.DataFrame,
    train_end: Optional[str] = None,
    test_start: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """train_end 之前为训练集，test_start 起为测试集（默认 2024-01-01）。"""
    train_end = train_end or Settings.TRAIN_END_DATE or DEFAULT_TRAIN_END
    test_start = test_start or Settings.TEST_START_DATE or DEFAULT_TEST_START
    t_end = pd.Timestamp(train_end)
    t_start = pd.Timestamp(test_start)
    train_df = df[df["Date"] < t_end].copy()
    test_df = df[df["Date"] >= t_start].copy()
    return train_df, test_df


def feature_columns(mode: str) -> list[str]:
    if is_fusion_mode(mode):
        return ["Close", "signed_score"]
    return ["Close"]


def build_sequences(
    df: pd.DataFrame,
    mode: str,
    seq_length: int = SEQ_LENGTH,
    train_ratio: float = 0.8,
    train_end: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, object, pd.DataFrame, dict]:
    """
    在训练集（默认 Date < 2024-01-01）上构建序列；验证为训练集内后 20% 时间序列。
    返回 meta 含 train_period / val_period 说明。
    """
    from sklearn.preprocessing import MinMaxScaler

    train_df, _ = split_train_test(df, train_end=train_end)
    if len(train_df) < seq_length + 10:
        sym = df["Symbol"].iloc[0] if "Symbol" in df.columns else "?"
        raise ValueError(f"{sym} 训练集过短（<{train_end}），rows={len(train_df)}")

    cols = feature_columns(mode)
    work = train_df[cols].astype(float).copy()
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(work.values)

    x_all, y_all = [], []
    for i in range(len(scaled) - seq_length):
        x_all.append(scaled[i : i + seq_length])
        y_all.append(scaled[i + seq_length, 0])

    x_all = np.array(x_all)
    y_all = np.array(y_all)
    if len(x_all) == 0:
        raise ValueError(f"样本不足 seq_length={seq_length}")

    n_train = int(len(x_all) * train_ratio)
    x_train, y_train = x_all[:n_train], y_all[:n_train]
    x_val, y_val = x_all[n_train:], y_all[n_train:]

    val_start_idx = n_train + seq_length
    val_start_date = (
        str(train_df["Date"].iloc[min(val_start_idx, len(train_df) - 1)].date())
        if len(train_df) > val_start_idx
        else str(train_df["Date"].iloc[-1].date())
    )

    meta = {
        "train_end_exclusive": train_end or Settings.TRAIN_END_DATE,
        "train_rows": len(train_df),
        "train_date_from": str(train_df["Date"].iloc[0].date()),
        "train_date_to": str(train_df["Date"].iloc[-1].date()),
        "in_train_val_from": val_start_date,
        "note": "2024 及以后未参与训练，仅用于 evaluate / 样本外预测",
    }

    scaled_df = pd.DataFrame(scaled, columns=cols)
    return x_train, y_train, x_val, y_val, scaler, scaled_df, meta
