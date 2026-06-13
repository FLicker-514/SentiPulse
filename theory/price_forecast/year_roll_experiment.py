"""
FinBERT fusion 逐年扩展训练窗口实验：考察训练数据量对 LSTM 预测的影响。

默认折（expanding）：
  (1) 2021 训练 → 2022 测试
  (2) 2021–2022 训练 → 2023 测试
  (3) 2021–2023 训练 → 2024 测试
  … 直至测试年无足够交易日

输出：data/experiments/year_roll_fusion/results.csv + results.json
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from theory.price_forecast.data_loader import feature_columns, load_merged_symbol
from theory.price_forecast.lstm_predictor import forecast_from_dataframe
from theory.price_forecast.model_factory import build_lstm
from theory.shared.paths import (
    CLEANED_CSV,
    FORECAST_HORIZON,
    MODEL_FUSION,
    PROCESSED_DIR,
    SEQ_LENGTH,
)

EXPERIMENT_DIR = PROCESSED_DIR / "experiments" / "year_roll_fusion"
DEFAULT_OUTPUT_CSV = EXPERIMENT_DIR / "results.csv"
DEFAULT_OUTPUT_JSON = EXPERIMENT_DIR / "results.json"


@dataclass
class YearFold:
    fold_id: int
    train_start: str
    train_end: str  # exclusive
    test_start: str
    test_end: str  # exclusive
    test_year: int
    train_years: int
    train_label: str


def generate_expanding_folds(
    first_train_year: int = 2021,
    last_test_year: Optional[int] = None,
) -> List[YearFold]:
    """累积扩展训练窗：训练集从 first_train_year 起逐年变长，测试年为下一年。"""
    folds: List[YearFold] = []
    max_test = last_test_year or datetime.now().year
    fold_id = 0
    for test_year in range(first_train_year + 1, max_test + 1):
        fold_id += 1
        train_years = test_year - first_train_year
        train_label = (
            str(first_train_year)
            if train_years == 1
            else f"{first_train_year}–{test_year - 1}"
        )
        folds.append(
            YearFold(
                fold_id=fold_id,
                train_start=f"{first_train_year}-01-01",
                train_end=f"{test_year}-01-01",
                test_start=f"{test_year}-01-01",
                test_end=f"{test_year + 1}-01-01",
                test_year=test_year,
                train_years=train_years,
                train_label=train_label,
            )
        )
    return folds


def _slice_period(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    return df[(df["Date"] >= t0) & (df["Date"] < t1)].copy()


def _build_train_arrays(
    train_df: pd.DataFrame,
    mode: str,
    seq_length: int = SEQ_LENGTH,
    train_ratio: float = 0.8,
):
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
    if len(x_all) < 10:
        raise ValueError(f"训练样本不足: {len(x_all)} (需要 >= 10)")

    n_train = max(1, int(len(x_all) * train_ratio))
    if n_train >= len(x_all):
        n_train = len(x_all) - 1
    x_train, y_train = x_all[:n_train], y_all[:n_train]
    x_val, y_val = x_all[n_train:], y_all[n_train:]
    return x_train, y_train, x_val, y_val, scaler


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mse = float(np.mean((y_true - y_pred) ** 2))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return {"mse": round(mse, 8), "mae": round(mae, 8)}


def _pct(a: float, b: float) -> float:
    return ((a - b) / b * 100) if b else 0.0


def _direction_correct(pred_avg: float, actual_avg: float, base: float) -> bool:
    return (pred_avg >= base) == (actual_avg >= base)


def backtest_on_period(
    df: pd.DataFrame,
    mode: str,
    model,
    scaler,
    test_start: str,
    test_end: str,
    horizon: int = FORECAST_HORIZON,
) -> dict:
    ref_df = df.sort_values("Date").reset_index(drop=True)
    t0, t1 = pd.Timestamp(test_start), pd.Timestamp(test_end)

    eval_indices = [
        i
        for i in range(SEQ_LENGTH, len(ref_df) - horizon)
        if t0 <= ref_df["Date"].iloc[i] < t1
    ]
    if not eval_indices:
        raise ValueError(f"测试窗 {test_start} ~ {test_end} 无有效截面")

    avg_errs, d1_errs, dir_hits, ret_errs = [], [], [], []
    for idx in eval_indices:
        actual_slice = ref_df.iloc[idx + 1 : idx + 1 + horizon]
        if len(actual_slice) < horizon:
            continue
        actual_prices = actual_slice["Close"].astype(float).tolist()
        actual_avg = float(np.mean(actual_prices))
        last_close = float(ref_df["Close"].iloc[idx])
        actual_ret = _pct(actual_avg, last_close)

        hist = ref_df.iloc[: idx + 1].copy()
        pred = forecast_from_dataframe(hist, mode, model, scaler, horizon=horizon)
        pred_avg = pred["avg_lstm_price"]
        pred_ret = _pct(pred_avg, last_close)

        avg_errs.append(abs(pred_avg - actual_avg))
        d1_errs.append(abs(pred["forecast_7d"][0]["predicted_close"] - actual_prices[0]))
        dir_hits.append(_direction_correct(pred_avg, actual_avg, last_close))
        ret_errs.append(abs(pred_ret - actual_ret))

    if not avg_errs:
        raise ValueError("测试窗内无完整 7 日预测截面")

    return {
        "n_eval_points": len(avg_errs),
        "mae_avg_7d_price": round(float(np.mean(avg_errs)), 4),
        "mae_day1_price": round(float(np.mean(d1_errs)), 4),
        "mae_return_pct": round(float(np.mean(ret_errs)), 4),
        "direction_accuracy": round(float(np.mean(dir_hits)), 4),
        "rmse_avg_7d_price": round(float(np.sqrt(np.mean(np.array(avg_errs) ** 2))), 4),
    }


def run_single_fold(
    symbol: str,
    fold: YearFold,
    mode: str = MODEL_FUSION,
    epochs: int = 20,
    batch_size: int = 32,
    verbose: int = 0,
) -> dict:
    df = load_merged_symbol(symbol, mode)
    data_end = df["Date"].max() + pd.Timedelta(days=1)
    test_end = min(pd.Timestamp(fold.test_end), data_end)

    train_df = _slice_period(df, fold.train_start, fold.train_end)
    test_df = _slice_period(df, fold.test_start, test_end.strftime("%Y-%m-%d"))

    row = {
        "symbol": symbol,
        "mode": mode,
        "fold_id": fold.fold_id,
        "train_label": fold.train_label,
        "train_years": fold.train_years,
        "train_start": fold.train_start,
        "train_end_exclusive": fold.train_end,
        "test_year": fold.test_year,
        "test_start": fold.test_start,
        "test_end_exclusive": test_end.strftime("%Y-%m-%d"),
        "train_trading_days": len(train_df),
        "test_trading_days": len(test_df),
        "epochs": epochs,
        "status": "ok",
    }

    if len(train_df) < SEQ_LENGTH + 20:
        row["status"] = "skipped"
        row["error"] = f"训练交易日过少: {len(train_df)}"
        return row
    if len(test_df) < 20:
        row["status"] = "skipped"
        row["error"] = f"测试交易日过少: {len(test_df)}"
        return row

    try:
        x_train, y_train, x_val, y_val, scaler = _build_train_arrays(train_df, mode)
        model = build_lstm(x_train.shape[2])
        model.fit(x_train, y_train, epochs=epochs, batch_size=batch_size, verbose=verbose)

        train_pred = model.predict(x_train, verbose=0).flatten()
        row["train_seq_samples"] = int(len(x_train))
        row["val_seq_samples"] = int(len(x_val))
        row["train_mae"] = _metrics(y_train, train_pred)["mae"]
        if len(x_val):
            val_pred = model.predict(x_val, verbose=0).flatten()
            row["val_mae"] = _metrics(y_val, val_pred)["mae"]
            row["val_mse"] = _metrics(y_val, val_pred)["mse"]

        test_metrics = backtest_on_period(
            df,
            mode,
            model,
            scaler,
            fold.test_start,
            test_end.strftime("%Y-%m-%d"),
        )
        row.update({f"test_{k}": v for k, v in test_metrics.items()})
    except Exception as exc:
        row["status"] = "error"
        row["error"] = str(exc)

    return row


def list_all_symbols() -> List[str]:
    if not CLEANED_CSV.exists():
        raise FileNotFoundError(f"缺少 {CLEANED_CSV}，请先 python run.py setup-data")
    df = pd.read_csv(CLEANED_CSV, parse_dates=["Date"])
    return sorted(df["Symbol"].unique().tolist())


def run_year_roll_experiment(
    symbols: Optional[List[str]] = None,
    mode: str = MODEL_FUSION,
    epochs: int = 20,
    first_train_year: int = 2021,
    last_test_year: Optional[int] = None,
    output_csv: Optional[Path] = None,
    output_json: Optional[Path] = None,
    verbose: int = 0,
) -> dict:
    sym_list = symbols or list_all_symbols()
    folds = generate_expanding_folds(first_train_year, last_test_year)

    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = output_csv or DEFAULT_OUTPUT_CSV
    out_json = output_json or DEFAULT_OUTPUT_JSON

    rows: List[dict] = []
    total = len(sym_list) * len(folds)
    step = 0

    for symbol in sym_list:
        for fold in folds:
            step += 1
            print(
                f"\n[{step}/{total}] {symbol} | 折{fold.fold_id}: "
                f"训练 {fold.train_label} → 测试 {fold.test_year}"
            )
            row = run_single_fold(
                symbol, fold, mode=mode, epochs=epochs, verbose=verbose
            )
            rows.append(row)
            if row["status"] == "ok":
                print(
                    f"  训练 {row['train_trading_days']}天 / 测试 {row['test_trading_days']}天 | "
                    f"val_MAE={row.get('val_mae', 'n/a')} | "
                    f"test_MAE(7d)={row.get('test_mae_avg_7d_price', 'n/a')}"
                )
            else:
                print(f"  {row['status']}: {row.get('error', '')}")

    df_out = pd.DataFrame(rows)
    df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")

    ok_df = df_out[df_out["status"] == "ok"]
    summary_by_fold = []
    if not ok_df.empty and "test_mae_avg_7d_price" in ok_df.columns:
        for fold_id, grp in ok_df.groupby("fold_id"):
            summary_by_fold.append({
                "fold_id": int(fold_id),
                "train_label": grp["train_label"].iloc[0],
                "train_years": int(grp["train_years"].iloc[0]),
                "test_year": int(grp["test_year"].iloc[0]),
                "n_symbols": len(grp),
                "mean_train_days": round(grp["train_trading_days"].mean(), 1),
                "mean_test_mae_7d": round(grp["test_mae_avg_7d_price"].mean(), 4),
                "mean_test_mae_day1": round(grp["test_mae_day1_price"].mean(), 4),
                "mean_direction_acc": round(grp["test_direction_accuracy"].mean(), 4),
            })

    payload = {
        "experiment": "year_roll_fusion",
        "description": "FinBERT fusion LSTM：累积训练窗 vs 下一年测试，考察训练数据量影响",
        "mode": mode,
        "epochs": epochs,
        "fold_style": "expanding",
        "first_train_year": first_train_year,
        "symbols": sym_list,
        "folds": [asdict(f) for f in folds],
        "summary_by_fold": summary_by_fold,
        "results": rows,
        "output_csv": str(out_csv),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_csv = EXPERIMENT_DIR / "summary_by_fold.csv"
    if summary_by_fold:
        pd.DataFrame(summary_by_fold).to_csv(summary_csv, index=False, encoding="utf-8-sig")
        payload["summary_csv"] = str(summary_csv)

    print(f"\n✅ 结果已写入:\n  CSV: {out_csv}\n  JSON: {out_json}")
    if summary_by_fold:
        print(f"  汇总: {summary_csv}")
    return payload
