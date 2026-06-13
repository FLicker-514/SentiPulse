#!/usr/bin/env python3
"""
FinBERT fusion 逐年扩展训练实验（全股票）。

  cd SentiPulse
  python scripts/run_year_roll_experiment.py
  python scripts/run_year_roll_experiment.py --epochs 20 --last-test-year 2025
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from theory.price_forecast.year_roll_experiment import run_year_roll_experiment


def main():
    parser = argparse.ArgumentParser(
        description="FinBERT fusion：累积训练窗实验（考察训练数据量对 LSTM 的影响）"
    )
    parser.add_argument("--symbols", nargs="+", help="默认全部 10 只股票")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--first-train-year", type=int, default=2021)
    parser.add_argument(
        "--last-test-year",
        type=int,
        default=None,
        help="最后测试年份，默认自动到数据末年",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="结果 CSV 路径，默认 data/processed/experiments/year_roll_fusion/results.csv",
    )
    parser.add_argument("--verbose", type=int, default=0, help="Keras 训练日志级别")
    args = parser.parse_args()

    run_year_roll_experiment(
        symbols=args.symbols,
        epochs=args.epochs,
        first_train_year=args.first_train_year,
        last_test_year=args.last_test_year,
        output_csv=Path(args.output_csv) if args.output_csv else None,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
