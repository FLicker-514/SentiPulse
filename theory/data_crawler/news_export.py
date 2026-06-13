"""将证券时报 JSON 转为 CSMD 按日 CSV。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

import pandas as pd


def parse_news_datetime(time_text: str) -> Optional[str]:
    if not time_text:
        return None
    text = str(time_text).strip()
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    m = re.search(r"(\d{1,2})[-/月](\d{1,2})", text)
    if m:
        mo, d = m.groups()
        return f"{pd.Timestamp.today().year:04d}-{int(mo):02d}-{int(d):02d}"
    return None


def export_json_to_csmd_daily(
    raw_json: Path,
    code_name: str,
    ticker: str,
    out_news_dir: Path,
    append: bool = True,
) -> int:
    """
    读取 news_scraper 输出的 JSON，写入 data/processed/CSMD50/news/<股票>/<日期>.csv
    列：code_name, ticker, created_at, text
    """
    with open(raw_json, encoding="utf-8") as f:
        articles = json.load(f)
    if isinstance(articles, dict) and "error" in articles:
        raise ValueError(f"爬取失败记录: {raw_json}")

    by_date = defaultdict(list)
    for item in articles:
        date_str = parse_news_datetime(item.get("time", ""))
        if not date_str:
            continue
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        text = f"{title}。{content}" if title and content else (title or content)
        if not text:
            continue
        by_date[date_str].append(text)

    stock_dir = out_news_dir / code_name
    stock_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for date_str, texts in sorted(by_date.items()):
        out_path = stock_dir / f"{date_str}.csv"
        rows = [
            {
                "code_name": code_name,
                "ticker": ticker,
                "created_at": date_str,
                "text": t,
            }
            for t in texts
        ]
        new_df = pd.DataFrame(rows)
        if append and out_path.exists():
            old = pd.read_csv(out_path, encoding="utf-8-sig")
            new_df = pd.concat([old, new_df], ignore_index=True)
            new_df.drop_duplicates(subset=["text"], keep="last", inplace=True)
        new_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        written += len(texts)
    return written
