"""
A股股票数据采集: AKShare 为主, Baostock 为备用方案

策略优化:
- AKShare 快速尝试 1 次, 失败后整个股票切换为 Baostock
- Baostock 收集前复权/后复权/不复权三种数据
- 现有数据不覆盖 (UNIQUE 约束自动跳过)
"""

import random
import time
import logging

from config import (
    STOCKS,
    START_DATE_AK,
    END_DATE_AK,
    STOCK_DELAY_MIN,
    STOCK_DELAY_MAX,
)
from database import (
    init_db,
    insert_stock_rows,
    get_stock_count,
    get_stock_date_range,
    upsert_progress,
)

log = logging.getLogger("sentipulse")


def fetch_akshare(name: str, code: str, adjust: str) -> list[dict]:
    """使用 AKShare 获取历史日线数据"""
    import akshare as ak

    df = ak.stock_zh_a_hist(
        symbol=code,
        period="daily",
        start_date=START_DATE_AK,
        end_date=END_DATE_AK,
        adjust=adjust,
    )

    col_map = {
        "日期": "trade_date", "股票代码": "stock_code",
        "开盘": "open", "最高": "high", "最低": "low", "收盘": "close",
        "成交量": "volume", "成交额": "amount", "振幅": "amplitude",
        "涨跌幅": "pct_change", "涨跌额": "change", "换手率": "turnover",
    }

    rows = []
    for _, row in df.iterrows():
        r = {"stock_name": name, "adjust": adjust if adjust else "none"}
        for cn, en in col_map.items():
            val = row.get(cn)
            r[en] = float(val) if val is not None and cn not in ("日期", "股票代码") else str(val) if val is not None else None
        rows.append(r)
    return rows


def fetch_baostock(name: str, code: str, adjustflag: str) -> list[dict] | None:
    """使用 Baostock 获取历史日线数据"""
    import baostock as bs

    try:
        bs.login()
    except Exception:
        pass

    try:
        fields = "date,code,open,high,low,close,volume,amount,turn,pctChg"
        rs = bs.query_history_k_data_plus(
            f"sh.{code}",
            fields,
            start_date="2025-01-01",
            end_date="2026-06-06",
            frequency="d",
            adjustflag=adjustflag,
        )
        data_rows = []
        while (rs.error_code == "0") & rs.next():
            data_rows.append(rs.get_row_data())

        adjust_label = {"1": "hfq", "2": "qfq", "3": "none"}.get(adjustflag, "qfq")

        rows = []
        for r in data_rows:
            rows.append({
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
                "adjust": adjust_label,
            })
        return rows
    finally:
        try:
            bs.logout()
        except Exception:
            pass


def crawl_stock(name: str, code: str) -> int:
    """采集单只股票, AKShare 优先, 一次失败即切换 Baostock"""
    log.info("[STOCK] 开始采集 %s (%s)", name, code)

    existing = get_stock_count(code)
    date_range = get_stock_date_range(code)
    if date_range:
        log.info("[STOCK] %s 已有 %d 条 (%s ~ %s)", name, existing, *date_range)

    total = 0

    # 先用 AKShare 尝试一次 qfq
    akshare_ok = False
    try:
        rows = fetch_akshare(name, code, "qfq")
        if rows:
            n = insert_stock_rows(rows)
            total += n
            akshare_ok = True
            log.info("[STOCK] %s (%s) AKShare qfq: %d 条, 新增 %d", name, code, len(rows), n)
    except Exception as e:
        log.warning("[STOCK] %s (%s) AKShare 失败: %s, 切换 Baostock", name, code, e)

    if akshare_ok:
        # AKShare 可用, 继续采集 hfq 和 none
        for adjust, label in [("hfq", "hfq"), ("", "none")]:
            try:
                rows = fetch_akshare(name, code, adjust)
                if rows:
                    n = insert_stock_rows(rows)
                    total += n
                    log.info("[STOCK] %s (%s) AKShare %s: %d 条, 新增 %d", name, code, label, len(rows), n)
            except Exception as e:
                log.warning("[STOCK] %s (%s) AKShare %s 失败: %s", name, code, label, e)
            time.sleep(random.uniform(STOCK_DELAY_MIN, STOCK_DELAY_MAX))
    else:
        # AKShare 不可用, 全部用 Baostock
        for adjustflag, label in [("2", "qfq"), ("1", "hfq"), ("3", "none")]:
            try:
                rows = fetch_baostock(name, code, adjustflag)
                if rows:
                    n = insert_stock_rows(rows)
                    total += n
                    log.info("[STOCK] %s (%s) Baostock %s: %d 条, 新增 %d", name, code, label, len(rows), n)
            except Exception as e:
                log.error("[STOCK] %s (%s) Baostock %s 失败: %s", name, code, label, e)
            time.sleep(random.uniform(0.3, 0.8))

    upsert_progress("stock", code, status="completed", total_items=total)
    return total


def crawl_all_stocks() -> dict[str, int]:
    """采集所有目标企业的股票数据"""
    init_db()
    results = {}
    for name, code in STOCKS.items():
        try:
            n = crawl_stock(name, code)
            results[name] = n
        except Exception as e:
            log.error("[STOCK] %s (%s) 致命错误: %s", name, code, e)
            results[name] = 0
            upsert_progress("stock", code, status="failed", last_error=str(e))
    return results
