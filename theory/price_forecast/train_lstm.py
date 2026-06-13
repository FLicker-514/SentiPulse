"""兼容入口：等价于 train.py --mode ts-only。"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from theory.price_forecast.train import run_train
from theory.shared.paths import MODEL_TS_ONLY


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()
    run_train(mode=MODEL_TS_ONLY, symbols=args.symbols, epochs=args.epochs)


if __name__ == "__main__":
    main()
