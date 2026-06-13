#!/usr/bin/env python3
"""
独立脚本：生成 Bert / FinBERT2-large 日度情感特征。
服务器在 SentiPulse 目录运行：

  # fusion-bert：未微调 Bert（默认 ../models/Bert）
  # fusion：FinBERT2-large 预训练权重（默认 ../models/FinBERT2-large，无需微调）
  python scripts/build_sentiment_both.py --variant both --dataset CSMD50_merged --symbols 贵州茅台
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from theory.price_forecast.sentiment_features import build_daily_sentiment, news_root_for_dataset


def main():
    parser = argparse.ArgumentParser(description="生成 Bert/FinBERT 日度情感特征 CSV")
    parser.add_argument("--symbols", nargs="+", help="股票中文名，如 贵州茅台")
    parser.add_argument("--force", action="store_true", help="覆盖已有 CSV")
    parser.add_argument(
        "--variant",
        choices=["bert", "finbert", "both"],
        default="both",
        help="bert=未微调Bert; finbert=FinBERT2-large(预训练); both=两者都生成",
    )
    parser.add_argument(
        "--dataset",
        default="CSMD50_merged",
        help="新闻目录 data/processed/<dataset>/news",
    )
    args = parser.parse_args()

    news_root = news_root_for_dataset(args.dataset)
    if not news_root.is_dir():
        raise SystemExit(f"新闻目录不存在: {news_root}")

    variants = ["bert", "finbert"] if args.variant == "both" else [args.variant]
    for v in variants:
        print(f"\n========== build-sentiment: {v} ==========")
        build_daily_sentiment(
            symbols=args.symbols,
            force=args.force,
            variant=v,
            news_root=news_root,
        )


if __name__ == "__main__":
    main()
