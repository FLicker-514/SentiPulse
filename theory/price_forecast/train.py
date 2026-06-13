"""训练股价预测模型：ts-only（仅时序）与 fusion（价量+日度情感）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from theory.price_forecast.data_loader import (
    build_sequences,
    load_merged_symbol,
    split_train_test,
)
from theory.price_forecast.model_factory import build_lstm
from theory.price_forecast.sentiment_features import build_daily_sentiment, news_root_for_dataset
from theory.shared.paths import (
    ALL_TRAIN_MODES,
    CLEANED_CSV,
    MODEL_FUSION_BERT,
    MODEL_TS_ONLY,
    MODELS_DIR,
    is_fusion_mode,
    model_paths,
)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    mse = float(np.mean((y_true - y_pred) ** 2))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    return {"mse": round(mse, 8), "mae": round(mae, 8)}


def train_symbol(
    symbol: str,
    mode: str,
    epochs: int,
    batch_size: int = 32,
    train_end: Optional[str] = None,
) -> Optional[dict]:
    symbol = symbol.strip()
    df = load_merged_symbol(symbol, mode)
    train_df, test_df = split_train_test(df, train_end=train_end)
    if len(train_df) < 70:
        print(f"  skip {symbol}: train_rows={len(train_df)} (< {train_end or '2024-01-01'})")
        return None

    te = train_end or "2024-01-01"
    print(f"Training [{mode}] {symbol} | 训练<{te} ({len(train_df)}天), 留测2024+ ({len(test_df)}天)")
    x_train, y_train, x_val, y_val, scaler, _, split_meta = build_sequences(
        df, mode, train_end=train_end
    )
    n_features = x_train.shape[2]
    model = build_lstm(n_features)
    model.fit(x_train, y_train, epochs=epochs, batch_size=batch_size, verbose=1)

    train_pred = model.predict(x_train, verbose=0).flatten()
    val_pred = model.predict(x_val, verbose=0).flatten() if len(x_val) else np.array([])

    metrics = {
        "symbol": symbol,
        "mode": mode,
        "n_features": n_features,
        "train_samples": int(len(x_train)),
        "val_samples": int(len(x_val)),
        "data_split": split_meta,
        "train": _metrics(y_train, train_pred),
    }
    if len(x_val):
        metrics["val"] = _metrics(y_val, val_pred)

    model_path, scaler_path = model_paths(symbol, mode)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(model_path)
    joblib.dump(scaler, scaler_path)
    meta_path = model_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  saved -> {model_path.name}")
    if "val" in metrics:
        print(f"  val MAE={metrics['val']['mae']:.6f} MSE={metrics['val']['mse']:.6f}")
    return metrics


def run_train(
    mode: str,
    symbols: Optional[List[str]] = None,
    epochs: int = 10,
    rebuild_sentiment: bool = False,
    train_end: Optional[str] = None,
    news_root: Optional[Path] = None,
) -> List[dict]:
    if mode == "all":
        all_results = []
        for m in ALL_TRAIN_MODES:
            print(f"\n========== 训练模式: {m} ==========")
            all_results.extend(
                run_train(
                    mode=m,
                    symbols=symbols,
                    epochs=epochs,
                    rebuild_sentiment=rebuild_sentiment,
                    train_end=train_end,
                    news_root=news_root,
                )
            )
        return all_results

    if mode not in ALL_TRAIN_MODES:
        raise ValueError(f"mode 须为 {ALL_TRAIN_MODES} 或 all")

    if not CLEANED_CSV.exists():
        raise SystemExit(f"缺少 {CLEANED_CSV}，请先 python run.py setup-data")

    if is_fusion_mode(mode):
        variant = "bert" if mode == MODEL_FUSION_BERT else "finbert"
        print(f"构建日度情感特征（{variant}）...")
        build_daily_sentiment(
            symbols=symbols,
            force=rebuild_sentiment,
            mode=mode,
            news_root=news_root,
        )

    df = pd.read_csv(CLEANED_CSV, parse_dates=["Date"])
    sym_list = symbols or sorted(df["Symbol"].unique().tolist())
    results = []
    for sym in sym_list:
        m = train_symbol(sym.strip(), mode, epochs, train_end=train_end)
        if m:
            results.append(m)
    return results


def main():
    parser = argparse.ArgumentParser(description="训练 ts-only / fusion LSTM")
    parser.add_argument(
        "--mode",
        choices=[*ALL_TRAIN_MODES, "all"],
        default=MODEL_TS_ONLY,
        help="ts-only | fusion-bert(未微调Bert) | fusion(FinBERT-zh) | all",
    )
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--rebuild-sentiment", action="store_true")
    parser.add_argument(
        "--train-end",
        default=None,
        help="训练集截止日期（不含），默认 2024-01-01",
    )
    parser.add_argument(
        "--dataset",
        default="CSMD50_merged",
        help="融合训练时新闻目录 data/processed/<dataset>/news",
    )
    args = parser.parse_args()
    news_root = news_root_for_dataset(args.dataset) if args.dataset else None
    run_train(
        mode=args.mode,
        symbols=args.symbols,
        epochs=args.epochs,
        rebuild_sentiment=args.rebuild_sentiment,
        train_end=args.train_end,
        news_root=news_root,
    )


if __name__ == "__main__":
    main()
