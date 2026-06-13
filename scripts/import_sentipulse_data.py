#!/usr/bin/env python3
"""
将本仓库 data_clean 清洗后的股票与新闻，
转换为 CSMD50 标准格式，并与既有历史数据合并。

输出目录（默认）：
  data/processed/CSMD50_merged/
    price/<股票名>.csv          # Date,Open,High,Low,Close,Adj Close,Volume
    news/<股票名>/<日期>.csv    # code_name,ticker,created_at,text

用法：
  python scripts/import_sentipulse_data.py
  python scripts/import_sentipulse_data.py --only-2025   # 仅写入 2025+，不合并旧数据
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

STOCK_CODE_TO_NAME: dict[str, str] = {
    "601328": "交通银行",
    "600048": "保利发展",
    "600406": "国电南瑞",
    "601398": "工商银行",
    "600276": "恒瑞医药",
    "688041": "海光信息",
    "603288": "海天味业",
    "600690": "海尔智家",
    "600519": "贵州茅台",
    "688111": "金山办公",
}
NAME_TO_CODE = {v: k for k, v in STOCK_CODE_TO_NAME.items()}

DEFAULT_STOCK_CSV = ROOT / "data_clean" / "output" / "stock_daily_cleaned.csv"
DEFAULT_NEWS_CSV = ROOT / "data_clean" / "output" / "news_summarized.csv"
DEFAULT_EXISTING = ROOT / "data" / "processed" / "CSMD50"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "CSMD50_merged"
CUTOFF_DATE = "2025-01-01"


def to_ticker(code: str) -> str:
    code = str(code).strip()
    prefix = "sh" if code.startswith(("6", "9")) else "sz"
    return f"{prefix}.{code}"


def parse_date(value: str) -> str | None:
    if not value or pd.isna(value):
        return None
    text = str(value).strip()
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if not m:
        return None
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def copy_existing_tree(src: Path, dst: Path) -> tuple[int, int]:
    price_count = 0
    news_count = 0
    if not src.is_dir():
        return price_count, news_count

    dst_price = dst / "price"
    dst_news = dst / "news"
    dst_price.mkdir(parents=True, exist_ok=True)
    dst_news.mkdir(parents=True, exist_ok=True)

    for f in src.glob("price/*.csv"):
        shutil.copy2(f, dst_price / f.name)
        price_count += 1

    for stock_dir in src.glob("news/*"):
        if not stock_dir.is_dir():
            continue
        target = dst_news / stock_dir.name
        target.mkdir(parents=True, exist_ok=True)
        for f in stock_dir.glob("*.csv"):
            shutil.copy2(f, target / f.name)
            news_count += 1

    return price_count, news_count


def import_price(
    stock_csv: Path,
    out_price_dir: Path,
    merge_existing: bool,
    min_date: str = CUTOFF_DATE,
) -> dict[str, int]:
    df = pd.read_csv(stock_csv, dtype={"StockCode": str})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"] >= pd.Timestamp(min_date)]
    df["StockCode"] = df["StockCode"].astype(str).str.zfill(6)

    stats: dict[str, int] = {}
    out_price_dir.mkdir(parents=True, exist_ok=True)

    for code, name in STOCK_CODE_TO_NAME.items():
        part = df[df["StockCode"] == code].copy()
        if part.empty:
            stats[name] = 0
            continue

        part = part.sort_values("Date")
        out_cols = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
        new_df = part[out_cols].copy()
        new_df["Date"] = new_df["Date"].dt.strftime("%Y-%m-%d")
        for col in ["Open", "High", "Low", "Close", "Adj Close"]:
            new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
        new_df["Volume"] = pd.to_numeric(new_df["Volume"], errors="coerce").round().astype("Int64")

        out_path = out_price_dir / f"{name}.csv"
        if merge_existing and out_path.exists():
            old = pd.read_csv(out_path)
            old["Date"] = pd.to_datetime(old["Date"], errors="coerce")
            old = old[old["Date"] < pd.Timestamp(min_date)]
            old["Date"] = old["Date"].dt.strftime("%Y-%m-%d")
            merged = pd.concat([old, new_df], ignore_index=True)
            merged = merged.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
            merged.to_csv(out_path, index=False, encoding="utf-8-sig")
            stats[name] = len(new_df)
        else:
            new_df.to_csv(out_path, index=False, encoding="utf-8-sig")
            stats[name] = len(new_df)

    return stats


def write_news_day_file(
    out_path: Path,
    code_name: str,
    ticker: str,
    date_str: str,
    texts: list[str],
    append: bool = True,
) -> int:
    rows = [
        {
            "code_name": code_name,
            "ticker": ticker,
            "created_at": date_str,
            "text": t.strip(),
        }
        for t in texts
        if t and str(t).strip()
    ]
    if not rows:
        return 0

    new_df = pd.DataFrame(rows)
    if append and out_path.exists():
        old = pd.read_csv(out_path, encoding="utf-8-sig")
        merged = pd.concat([old, new_df], ignore_index=True)
        merged.drop_duplicates(subset=["text"], keep="last", inplace=True)
        merged.to_csv(out_path, index=False, encoding="utf-8-sig")
        return len(rows)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return len(rows)


def import_news(
    news_csv: Path,
    out_news_dir: Path,
    min_date: str = CUTOFF_DATE,
) -> dict[str, int]:
    df = pd.read_csv(news_csv, dtype=str).fillna("")
    by_day: dict[tuple[str, str], list[str]] = defaultdict(list)

    for _, row in df.iterrows():
        name = row.get("企业", "").strip()
        if name not in NAME_TO_CODE:
            continue
        date_str = parse_date(row.get("日期", ""))
        if not date_str or date_str < min_date:
            continue
        text = row.get("内容", "").strip()
        if not text:
            continue
        by_day[(name, date_str)].append(text)

    stats: dict[str, int] = defaultdict(int)
    for (name, date_str), texts in sorted(by_day.items()):
        ticker = to_ticker(NAME_TO_CODE[name])
        out_path = out_news_dir / name / f"{date_str}.csv"
        n = write_news_day_file(out_path, name, ticker, date_str, texts, append=True)
        stats[name] += n

    return dict(stats)


def main():
    parser = argparse.ArgumentParser(description="导入 SentiPulse 2025+ 数据到 CSMD50 格式")
    parser.add_argument("--stock-csv", type=Path, default=DEFAULT_STOCK_CSV)
    parser.add_argument("--news-csv", type=Path, default=DEFAULT_NEWS_CSV)
    parser.add_argument("--existing", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--only-2025",
        action="store_true",
        help="不复制旧 CSMD50，仅输出 2025+ 数据",
    )
    parser.add_argument("--min-date", default=CUTOFF_DATE, help="仅导入该日期及以后的数据")
    args = parser.parse_args()

    if not args.stock_csv.exists():
        raise SystemExit(f"缺少股票文件: {args.stock_csv}")
    if not args.news_csv.exists():
        raise SystemExit(f"缺少新闻文件: {args.news_csv}")

    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    copied_price = copied_news = 0
    if not args.only_2025:
        copied_price, copied_news = copy_existing_tree(args.existing, args.output)
        print(f"[复制历史] price={copied_price} 只, news={copied_news} 个日文件")

    price_stats = import_price(
        args.stock_csv,
        args.output / "price",
        merge_existing=not args.only_2025,
        min_date=args.min_date,
    )
    news_stats = import_news(args.news_csv, args.output / "news", min_date=args.min_date)

    print(f"\n[输出目录] {args.output}")
    print("\n[2025+ 股票行数]")
    for name, n in sorted(price_stats.items()):
        print(f"  {name}: {n}")

    print("\n[2025+ 新闻条数]")
    for name, n in sorted(news_stats.items()):
        print(f"  {name}: {n}")

    print("\n[下一步]")
    print("  python run.py setup-data --dataset CSMD50_merged --rebuild")
    print("  python scripts/build_sentiment_both.py --variant both")
    print("  python -m theory.price_forecast.train --mode all --symbols 贵州茅台")


if __name__ == "__main__":
    main()
