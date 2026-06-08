"""
Build SQLite database from CSV files.

Usage:
    uv run python data/build_db.py

Output: data/sentipulse.db (4 tables)
"""

import csv
import os
import sqlite3

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "sentipulse.db")

TABLES = [
    {
        "name": "stock_daily",
        "csv": "stock/stock_daily.csv",
        "columns": [
            ("StockCode", "TEXT"),
            ("Date", "TEXT"),
            ("Open", "REAL"),
            ("High", "REAL"),
            ("Low", "REAL"),
            ("Close", "REAL"),
            ("Adj Close", "REAL"),
            ("Volume", "REAL"),
        ],
        "indexes": ["StockCode", "Date"],
    },
    {
        "name": "news_eastmoney",
        "csv": "news/news_eastmoney.csv",
        "columns": [
            ("企业名称", "TEXT"),
            ("标题", "TEXT"),
            ("URL", "TEXT"),
            ("发布时间", "TEXT"),
            ("来源", "TEXT"),
            ("正文", "TEXT"),
        ],
        "indexes": ["企业名称", "发布时间"],
    },
    {
        "name": "news_cninfo",
        "csv": "news/news_cninfo.csv",
        "columns": [
            ("企业名称", "TEXT"),
            ("标题", "TEXT"),
            ("URL", "TEXT"),
            ("发布时间", "TEXT"),
            ("来源", "TEXT"),
            ("正文", "TEXT"),
        ],
        "indexes": ["企业名称", "发布时间"],
    },
    {
        "name": "news_stcn",
        "csv": "news/news_stcn.csv",
        "columns": [
            ("企业名称", "TEXT"),
            ("标题", "TEXT"),
            ("URL", "TEXT"),
            ("发布时间", "TEXT"),
            ("来源", "TEXT"),
            ("摘要", "TEXT"),
            ("正文", "TEXT"),
        ],
        "indexes": ["企业名称", "发布时间"],
    },
]


def build() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    for table in TABLES:
        csv_path = os.path.join(DATA_DIR, table["csv"])
        col_defs = ", ".join(f'"{c}" {t}' for c, t in table["columns"])
        col_names = [c for c, _ in table["columns"]]

        db.execute(f'CREATE TABLE {table["name"]} ({col_defs})')

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = [tuple(row[c] for c in col_names) for row in reader]

        placeholders = ", ".join("?" for _ in col_names)
        quoted_cols = ", ".join(f'"{c}"' for c in col_names)
        db.executemany(
            f'INSERT INTO {table["name"]} ({quoted_cols}) VALUES ({placeholders})',
            rows,
        )
        db.commit()

        for idx_col in table["indexes"]:
            db.execute(
                f'CREATE INDEX IF NOT EXISTS idx_{table["name"]}_{idx_col} '
                f'ON {table["name"]}("{idx_col}")'
            )
        db.commit()

        print(f"  {table['name']}: {len(rows)} rows")

    db.close()

    size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"\nDone: {DB_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    build()
