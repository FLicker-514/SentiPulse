"""
SentiPulse data collection main program.

Usage:
    cd data_crawler
    uv run python main.py              # full collection (stock + news)
    uv run python main.py --stock      # stock only
    uv run python main.py --news       # news only
    uv run python main.py --status     # show data statistics
"""

import argparse
import logging
import sys
import time

from logger import setup_logger

log: logging.Logger | None = None


def run_stock_crawler() -> None:
    from stock.stock_crawler import crawl_all_stocks

    log.info("=" * 60)
    log.info("Starting stock data collection")
    log.info("=" * 60)

    results = crawl_all_stocks()

    log.info("=" * 60)
    log.info("Stock collection complete:")
    total = 0
    for name, count in results.items():
        log.info("  %s: %d rows", name, count)
        total += count
    log.info("  Total new: %d rows", total)
    log.info("=" * 60)


def run_news_crawler() -> None:
    from news.news_crawler import crawl_all_news

    log.info("=" * 60)
    log.info("Starting news data collection")
    log.info("=" * 60)

    results = crawl_all_news()

    log.info("=" * 60)
    log.info("News collection complete:")
    total = 0
    for name, count in results.items():
        log.info("  %s: %d articles", name, count)
        total += count
    log.info("  Total new: %d articles", total)
    log.info("=" * 60)


def show_status() -> None:
    from database import init_db, get_stock_count, get_news_count, get_stock_date_range
    from config import STOCKS

    init_db()

    print("\n" + "=" * 60)
    print("  SentiPulse Data Status")
    print("=" * 60)

    print("\n  [Stock Data] stock_daily:")
    for name, code in STOCKS.items():
        count = get_stock_count(code)
        dr = get_stock_date_range(code)
        range_str = f"{dr[0]} ~ {dr[1]}" if dr else "N/A"
        print(f"    {name:6s} ({code}): {count:4d} rows | {range_str}")
    print(f"    Total: {get_stock_count()} rows")

    print("\n  [News Data] news_articles:")
    for name in STOCKS:
        count = get_news_count(name)
        print(f"    {name:6s}: {count:4d} articles")
    print(f"    Total: {get_news_count()} articles")

    print("\n    DB: data/sentipulse.db")
    print("    Log: logs/crawler.log")
    print("=" * 60 + "\n")


def main() -> None:
    global log
    log = setup_logger()

    parser = argparse.ArgumentParser(description="SentiPulse data collection tool")
    parser.add_argument("--stock", action="store_true", help="Stock data only")
    parser.add_argument("--news", action="store_true", help="News data only")
    parser.add_argument("--status", action="store_true", help="Show data statistics")
    args = parser.parse_args()

    start = time.time()

    if args.status:
        show_status()
    elif args.stock:
        run_stock_crawler()
    elif args.news:
        run_news_crawler()
    else:
        run_stock_crawler()
        log.info("")
        run_news_crawler()

    elapsed = time.time() - start
    log.info("Elapsed: %.1f sec (%.1f min)", elapsed, elapsed / 60)

    if not args.status:
        show_status()


if __name__ == "__main__":
    main()
