"""从 CSMD 新闻目录随机抽样，批量测试 FinBERT 情感。"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

from theory.shared.paths import CSMD_RAW_DIR


@dataclass
class NewsItem:
    symbol: str
    date: str
    text: str
    source_file: str


def iter_news_items(
    news_root: Optional[Path] = None,
    symbol: Optional[str] = None,
) -> Iterator[NewsItem]:
    """遍历 news/<股票>/<日期>.csv 中每条 text。"""
    root = news_root or (CSMD_RAW_DIR / "news")
    if not root.is_dir():
        raise FileNotFoundError(f"新闻目录不存在: {root}")

    if symbol:
        dirs = [root / symbol.strip()]
        if not dirs[0].is_dir():
            raise FileNotFoundError(f"未找到股票新闻目录: {dirs[0]}")
    else:
        dirs = sorted(p for p in root.iterdir() if p.is_dir())

    for sym_dir in dirs:
        sym = sym_dir.name
        for csv_path in sorted(sym_dir.glob("*.csv")):
            date = csv_path.stem
            try:
                with open(csv_path, encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        text = (row.get("text") or "").strip()
                        if not text:
                            continue
                        yield NewsItem(
                            symbol=sym,
                            date=row.get("created_at") or date,
                            text=text,
                            source_file=str(csv_path.relative_to(root.parent.parent)),
                        )
            except OSError:
                continue


def collect_news_pool(
    news_root: Optional[Path] = None,
    symbol: Optional[str] = None,
    max_pool: int = 50000,
) -> List[NewsItem]:
    pool: List[NewsItem] = []
    for item in iter_news_items(news_root, symbol=symbol):
        pool.append(item)
        if len(pool) >= max_pool:
            break
    return pool


def sample_news(
    n: int,
    symbol: Optional[str] = None,
    seed: Optional[int] = None,
    news_root: Optional[Path] = None,
) -> List[NewsItem]:
    """随机抽取 n 条新闻（无放回；池子不足时返回全部）。"""
    if n <= 0:
        return []
    pool = collect_news_pool(news_root, symbol=symbol)
    if not pool:
        raise FileNotFoundError("未找到可用新闻，请先运行 python run.py setup-data")
    rng = random.Random(seed)
    k = min(n, len(pool))
    return rng.sample(pool, k)


def run_sentiment_batch(
    n: int,
    symbol: Optional[str] = None,
    seed: Optional[int] = None,
    news_root: Optional[Path] = None,
) -> List[dict]:
    from theory.sentiment_model.inference import sentiment_probabilities

    items = sample_news(n, symbol=symbol, seed=seed, news_root=news_root)
    results = []
    for i, item in enumerate(items, 1):
        sent = sentiment_probabilities(item.text)
        results.append(
            {
                "index": i,
                "symbol": item.symbol,
                "date": item.date,
                "source_file": item.source_file,
                "text_preview": item.text[:120] + ("..." if len(item.text) > 120 else ""),
                "sentiment": sent,
            }
        )
    return results
