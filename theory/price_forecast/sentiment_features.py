"""按交易日聚合新闻情感，生成与行情对齐的日度特征。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional

import pandas as pd

from theory.shared.paths import (
    CSMD_RAW_DIR,
    PROCESSED_DIR,
    SENTIMENT_DAILY_BERT_CSV,
    SENTIMENT_DAILY_CSV,
    resolve_sentiment_model_dir,
    sentiment_variant_for_mode,
)


def _sentiment_for_texts(texts: List[str], variant: str = "finbert") -> dict:
    from theory.sentiment_model.inference import sentiment_probabilities

    combined = " ".join(t for t in texts if t and str(t).strip())
    if not combined.strip():
        return {
            "signed_score": 0.0,
            "positive": 0.0,
            "negative": 0.0,
            "label": "neutral",
            "confidence": 0.0,
        }
    return sentiment_probabilities(combined, variant=variant)


def _output_csv_for_variant(variant: str) -> Path:
    return SENTIMENT_DAILY_BERT_CSV if variant == "bert" else SENTIMENT_DAILY_CSV


def build_daily_sentiment(
    symbols: Optional[List[str]] = None,
    news_root: Optional[Path] = None,
    force: bool = False,
    variant: str = "finbert",
    mode: Optional[str] = None,
) -> pd.DataFrame:
    """
    扫描 news/<股票>/<日期>.csv，用 Bert / FinBERT 得到每日 signed_score。

    variant: bert | finbert
    mode: 若提供 fusion / fusion-bert，则自动选择 variant 与输出 CSV。
    """
    if mode:
        variant = sentiment_variant_for_mode(mode)

    variant = variant.strip().lower()
    if variant not in ("bert", "finbert"):
        raise ValueError(f"variant 须为 bert 或 finbert，收到: {variant}")

    out_csv = _output_csv_for_variant(variant)
    model_dir = resolve_sentiment_model_dir(variant)
    print(f"  情感模型 [{variant}]: {model_dir}")
    print(f"  输出 CSV: {out_csv}")

    if out_csv.exists() and not force:
        df = pd.read_csv(out_csv, parse_dates=["Date"])
        if symbols:
            df = df[df["Symbol"].isin([s.strip() for s in symbols])]
        return df

    root = news_root or (CSMD_RAW_DIR / "news")
    if not root.is_dir():
        raise FileNotFoundError(f"新闻目录不存在: {root}")

    sym_dirs = sorted(p for p in root.iterdir() if p.is_dir())
    if symbols:
        wanted = {s.strip() for s in symbols}
        sym_dirs = [p for p in sym_dirs if p.name in wanted]

    rows = []
    for sym_dir in sym_dirs:
        symbol = sym_dir.name
        csv_files = sorted(sym_dir.glob("*.csv"))
        print(f"  情感特征 [{variant}]: {symbol} ({len(csv_files)} 个交易日)")
        for csv_path in csv_files:
            texts = []
            date_str = csv_path.stem
            try:
                with open(csv_path, encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        t = (row.get("text") or "").strip()
                        if t:
                            texts.append(t)
                        if row.get("created_at"):
                            date_str = str(row["created_at"])[:10]
            except OSError:
                continue
            sent = _sentiment_for_texts(texts, variant=variant)
            rows.append(
                {
                    "Date": date_str,
                    "Symbol": symbol,
                    "signed_score": sent["signed_score"],
                    "positive": sent["positive"],
                    "negative": sent["negative"],
                    "label": sent["label"],
                    "confidence": sent["confidence"],
                }
            )

    if not rows:
        raise FileNotFoundError("未生成任何日度情感记录")

    out = pd.DataFrame(rows)
    out["Date"] = pd.to_datetime(out["Date"])
    out.sort_values(["Symbol", "Date"], inplace=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)
    print(f"已写入 {out_csv} ({len(out)} 行)")
    return out


def news_root_for_dataset(dataset: str) -> Path:
    return PROCESSED_DIR / dataset / "news"
