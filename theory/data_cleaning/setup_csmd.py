"""
(2) 数据清洗：将 CSMD 原始数据放入 data/processed/CSMD50/，并生成训练用 CSV + 新闻 JSON。

用法: python -m theory.data_cleaning.setup_csmd
或:   python run.py setup-data
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theory.shared.paths import (
    CLEANED_CSV,
    CSMD_NEWS_JSON,
    DATASETS_DIR,
    EXTERNAL_LIGHTQUANT,
    PROCESSED_DIR,
)
from theory.data_cleaning.symbols import list_symbols_from_data

# 复用复制与转换逻辑（原 scripts/setup_csmd_data.py）
import shutil  # noqa: E402


def resolve_source(dataset: str) -> Optional[Path]:
    ext = EXTERNAL_LIGHTQUANT / "dataset" / dataset
    if (ext / "price").is_dir():
        return ext
    return None


def copy_tree(src: Path, dst: Path) -> int:
    count = 0
    for sub in ("price", "news"):
        s = src / sub
        if not s.is_dir():
            continue
        d = dst / sub
        d.mkdir(parents=True, exist_ok=True)
        if sub == "price":
            for f in s.glob("*.csv"):
                shutil.copy2(f, d / f.name)
                count += 1
        else:
            for stock_dir in s.iterdir():
                if not stock_dir.is_dir():
                    continue
                target_dir = d / stock_dir.name
                target_dir.mkdir(parents=True, exist_ok=True)
                for f in stock_dir.glob("*.csv"):
                    shutil.copy2(f, target_dir / f.name)
                    count += 1
    return count


def convert_price_csv(src: Path, symbol: str) -> pd.DataFrame:
    df = pd.read_csv(src, parse_dates=["Date"])
    df = df.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    close_col = "Close" if "Close" in df.columns else "Adj Close"
    df["Close"] = pd.to_numeric(df[close_col], errors="coerce")
    for col in ["Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    out = pd.DataFrame()
    out["Date"] = df["Date"]
    out["Symbol"] = symbol
    out["Series"] = "EQ"
    out["Prev Close"] = df["Close"].shift(1)
    out.loc[out.index[0], "Prev Close"] = df["Open"].iloc[0]
    out["Open"] = df["Open"]
    out["High"] = df["High"]
    out["Low"] = df["Low"]
    out["Last"] = df["Close"]
    out["Close"] = df["Close"]
    out["VWAP"] = (out["High"] + out["Low"] + out["Close"]) / 3
    return out[
        ["Date", "Symbol", "Series", "Prev Close", "Open", "High", "Low", "Last", "Close", "VWAP"]
    ]


def aggregate_news(news_dir: Path, max_chars: int = 8000) -> str:
    if not news_dir.is_dir():
        return ""
    texts = []
    for csv_path in sorted(news_dir.glob("*.csv"), reverse=True):
        try:
            ndf = pd.read_csv(csv_path)
        except Exception:
            continue
        if "text" not in ndf.columns:
            continue
        for t in ndf["text"].dropna().astype(str):
            t = t.strip()
            if t:
                texts.append(t)
    combined = " ".join(texts)
    return combined[:max_chars] if len(combined) > max_chars else combined


def build_processed(raw_dir: Path, stocks: Optional[List[str]] = None) -> None:
    price_dir = raw_dir / "price"
    news_root = raw_dir / "news"
    stock_files = sorted(price_dir.glob("*.csv"))
    if stocks:
        wanted = set(stocks)
        stock_files = [p for p in stock_files if p.stem in wanted]
    if not stock_files:
        raise SystemExit(f"{price_dir} 下没有股票 CSV")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    news_map = {}
    dfs = []
    for path in stock_files:
        symbol = path.stem
        print(f"  处理: {symbol}")
        df = convert_price_csv(path, symbol)
        df.to_csv(DATASETS_DIR / f"{symbol}.csv", index=False)
        dfs.append(df)
        text = aggregate_news(news_root / symbol)
        if text:
            news_map[symbol] = text

    merged = pd.concat(dfs, ignore_index=True)
    merged.sort_values(["Symbol", "Date"], inplace=True)
    merged.to_csv(CLEANED_CSV, index=False)
    with open(CSMD_NEWS_JSON, "w", encoding="utf-8") as f:
        json.dump(news_map, f, ensure_ascii=False, indent=2)
    print(f"合并 -> {CLEANED_CSV} ({len(merged)} rows)")
    print(f"新闻 -> {CSMD_NEWS_JSON} ({len(news_map)} 只)")


def main():
    parser = argparse.ArgumentParser(description="CSMD 数据清洗与入库")
    parser.add_argument("--dataset", default="CSMD50")
    parser.add_argument("--stocks", nargs="+")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()

    raw_dst = PROCESSED_DIR / args.dataset  # data/processed/CSMD50
    if not args.rebuild:
        src = args.source or resolve_source(args.dataset)
        if src is None:
            if not ((raw_dst / "price").is_dir()):
                raise SystemExit("请先准备 LightQuant 数据或运行 (1) 数据爬取")
            print(f"使用已有: {raw_dst}")
        else:
            print(f"复制 {src} -> {raw_dst}")
            print(f"已复制 {copy_tree(src, raw_dst)} 个文件")

    build_processed(raw_dst, args.stocks)
    syms = list_symbols_from_data(raw_dst / "price")
    print("可用股票:", ", ".join(syms))


if __name__ == "__main__":
    main()
