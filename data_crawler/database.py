"""
SQLite 数据库管理层
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from config import DB_DIR, DB_PATH

_local = threading.local()


def get_db() -> sqlite3.Connection:
    """获取线程本地数据库连接"""
    if not hasattr(_local, "conn") or _local.conn is None:
        os.makedirs(DB_DIR, exist_ok=True)
        _local.conn = sqlite3.connect(DB_PATH)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.execute("PRAGMA cache_size=-64000")
    return _local.conn


@contextmanager
def transaction():
    """事务上下文管理器"""
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def init_db() -> None:
    """初始化数据库表"""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS stock_daily (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code  TEXT NOT NULL,
            stock_name  TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            volume      REAL,
            amount      REAL,
            amplitude   REAL,
            pct_change  REAL,
            change      REAL,
            turnover    REAL,
            adjust      TEXT DEFAULT 'qfq',
            fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code, trade_date, adjust)
        );

        CREATE INDEX IF NOT EXISTS idx_sd_code  ON stock_daily(stock_code);
        CREATE INDEX IF NOT EXISTS idx_sd_date  ON stock_daily(trade_date);
        CREATE INDEX IF NOT EXISTS idx_sd_name  ON stock_daily(stock_name);

        CREATE TABLE IF NOT EXISTS news_articles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name    TEXT NOT NULL,
            search_keyword  TEXT NOT NULL,
            title           TEXT,
            url             TEXT,
            publish_time    TEXT,
            source          TEXT,
            excerpt         TEXT,
            tags            TEXT,
            article_type    TEXT,
            full_content    TEXT,
            fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(url)
        );

        CREATE INDEX IF NOT EXISTS idx_na_company ON news_articles(company_name);
        CREATE INDEX IF NOT EXISTS idx_na_pubtime ON news_articles(publish_time);
        CREATE INDEX IF NOT EXISTS idx_na_url     ON news_articles(url);

        CREATE TABLE IF NOT EXISTS crawl_progress (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type       TEXT NOT NULL,
            task_key        TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            total_items     INTEGER DEFAULT 0,
            current_page    INTEGER DEFAULT 0,
            last_error      TEXT,
            started_at      TIMESTAMP,
            completed_at    TIMESTAMP,
            UNIQUE(task_type, task_key)
        );
    """)
    db.commit()


# --- 股票数据操作 ---

def insert_stock_rows(rows: list[dict]) -> int:
    """批量插入股票日线数据 (INSERT OR IGNORE 跳过重复)"""
    if not rows:
        return 0
    sql = """
        INSERT OR IGNORE INTO stock_daily
            (stock_code, stock_name, trade_date, open, high, low, close,
             volume, amount, amplitude, pct_change, change, turnover, adjust)
        VALUES (:stock_code, :stock_name, :trade_date, :open, :high, :low, :close,
                :volume, :amount, :amplitude, :pct_change, :change, :turnover, :adjust)
    """
    with transaction() as db:
        cur = db.executemany(sql, rows)
        return cur.rowcount


def get_stock_count(stock_code: str = None) -> int:
    db = get_db()
    if stock_code:
        return db.execute(
            "SELECT COUNT(*) FROM stock_daily WHERE stock_code=?", (stock_code,)
        ).fetchone()[0]
    return db.execute("SELECT COUNT(*) FROM stock_daily").fetchone()[0]


def get_stock_date_range(stock_code: str) -> tuple[str, str] | None:
    db = get_db()
    row = db.execute(
        "SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily WHERE stock_code=?",
        (stock_code,),
    ).fetchone()
    return row if row[0] else None


# --- 新闻数据操作 ---

def insert_news_rows(rows: list[dict]) -> int:
    """批量插入新闻 (INSERT OR IGNORE 通过 UNIQUE(url) 去重)"""
    if not rows:
        return 0
    sql = """
        INSERT OR IGNORE INTO news_articles
            (company_name, search_keyword, title, url, publish_time,
             source, excerpt, tags, article_type, full_content)
        VALUES (:company_name, :search_keyword, :title, :url, :publish_time,
                :source, :excerpt, :tags, :article_type, :full_content)
    """
    with transaction() as db:
        cur = db.executemany(sql, rows)
        return cur.rowcount


def get_news_count(company_name: str = None) -> int:
    db = get_db()
    if company_name:
        return db.execute(
            "SELECT COUNT(*) FROM news_articles WHERE company_name=?", (company_name,)
        ).fetchone()[0]
    return db.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]


def get_news_urls() -> set[str]:
    """获取已抓取的所有新闻URL"""
    db = get_db()
    return {row[0] for row in db.execute("SELECT url FROM news_articles").fetchall()}


# --- 进度管理 ---

def get_progress(task_type: str, task_key: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT status, current_page, total_items FROM crawl_progress WHERE task_type=? AND task_key=?",
        (task_type, task_key),
    ).fetchone()
    if row:
        return {"status": row[0], "current_page": row[1], "total_items": row[2]}
    return None


def upsert_progress(task_type: str, task_key: str, **kwargs) -> None:
    fields = list(kwargs.keys())
    values = list(kwargs.values())
    set_clause = ", ".join(f"{f}=?" for f in fields)
    now = datetime.now().isoformat()
    with transaction() as db:
        db.execute(
            f"""INSERT INTO crawl_progress (task_type, task_key, {", ".join(fields)}, started_at)
                VALUES (?, ?, {", ".join("?" for _ in fields)}, ?)
                ON CONFLICT(task_type, task_key) DO UPDATE SET {set_clause}, completed_at=?
                WHERE status != 'completed'
            """,
            (task_type, task_key, *values, now, *values, now),
        )


def get_pending_tasks(task_type: str) -> list[str]:
    db = get_db()
    rows = db.execute(
        "SELECT task_key FROM crawl_progress WHERE task_type=? AND status!='completed'",
        (task_type,),
    ).fetchall()
    return [r[0] for r in rows]
