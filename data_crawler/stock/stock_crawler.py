"""
A股股票数据采集: Baostock (前复权 + 后复权 + 不复权)
"""

import random
import time
import logging

from config import STOCKS
from database import (
    init_db,
    insert_stock_rows,
    get_stock_count,
    get_stock_date_range,
    upsert_progress,
    get_db,
)

log = logging.getLogger("sentipulse")


def fetch_baostock(name: str, code: str, adjustflag: str) -> list[dict] | None:
    import baostock as bs

    try:
        bs.login()
    except Exception:
        pass

    try:
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        rs = bs.query_history_k_data_plus(
            f"{prefix}.{code}",
            "date,code,open,high,low,close,volume,amount,turn,pctChg",
            start_date="2025-01-01",
            end_date="2026-06-06",
            frequency="d",
            adjustflag=adjustflag,
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        label = {"1": "hfq", "2": "qfq", "3": "none"}[adjustflag]

        result = []
        for r in rows:
            result.append({
                "stock_name": name,
                "trade_date": r[0],
                "stock_code": r[1].replace("sh.", "").replace("sz.", ""),
                "open": float(r[2]) if r[2] else None,
                "high": float(r[3]) if r[3] else None,
                "low": float(r[4]) if r[4] else None,
                "close": float(r[5]) if r[5] else None,
                "volume": float(r[6]) if r[6] else None,
                "amount": float(r[7]) if r[7] else None,
                "turnover": float(r[8]) if r[8] else None,
                "pct_change": float(r[9]) if r[9] else None,
                "change": None,
                "amplitude": None,
                "adjust": label,
            })
        return result
    finally:
        try:
            bs.logout()
        except Exception:
            pass


def crawl_stock(name: str, code: str) -> int:
    log.info("[STOCK] %s (%s)", name, code)
    total = 0

    for adjustflag, label in [("2", "qfq"), ("1", "hfq"), ("3", "none")]:
        try:
            rows = fetch_baostock(name, code, adjustflag)
            if rows:
                n = insert_stock_rows(rows)
                total += n
                log.info("[STOCK]   %s: %d rows, %d new", label, len(rows), n)
        except Exception as e:
            log.error("[STOCK]   %s: %s", label, e)
        time.sleep(random.uniform(0.3, 0.8))

    upsert_progress("stock", code, status="completed", total_items=total)
    return total


def crawl_all_stocks() -> dict[str, int]:
    init_db()

    # Clear old AKShare data (had incorrect "none" data)
    get_db().execute("DELETE FROM stock_daily")
    get_db().commit()
    log.info("[STOCK] Old data cleared, re-collecting...")

    results = {}
    for name, code in STOCKS.items():
        try:
            n = crawl_stock(name, code)
            results[name] = n
        except Exception as e:
            log.error("[STOCK] %s (%s) error: %s", name, code, e)
            results[name] = 0
    return results
