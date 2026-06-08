"""
Cninfo 公告正文 PDF 下载与文本提取 (PyMuPDF)

PDF URL 格式: http://static.cninfo.com.cn/finalpage/{日期}/{公告ID}.PDF
从现有数据库记录中提取 announcementId 和日期, 直接构造 PDF URL 下载
"""

import logging
import random
import re
import time

import fitz  # PyMuPDF
import requests

from config import (
    USER_AGENTS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from database import init_db, get_db, transaction

log = logging.getLogger("sentipulse")

PDF_BASE = "http://static.cninfo.com.cn"


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _extract_pdf_text(pdf_url: str) -> str | None:
    """下载 PDF 并用 PyMuPDF 提取文本"""
    headers = {
        "User-Agent": _random_ua(),
        "Accept": "application/pdf,*/*",
        "Referer": "http://www.cninfo.com.cn/",
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(pdf_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                return None

            doc = fitz.open(stream=resp.content, filetype="pdf")
            try:
                texts = []
                for page in doc:
                    t = page.get_text()
                    if t:
                        texts.append(t)
                full_text = "\n".join(texts)
                full_text = re.sub(r"\n{3,}", "\n\n", full_text)
                return full_text[:10000]
            finally:
                doc.close()
        except Exception as e:
            log.debug("[CNPDF] Attempt %d: %s", attempt + 1, e)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF * (attempt + 1))

    return None


def backfill_content(limit: int = 0) -> int:
    """
    回填 Cninfo 公告正文:
    - 从 URL 解析 announcementId
    - 从 publish_time 提取日期
    - 构造 PDF URL: http://static.cninfo.com.cn/finalpage/{date}/{id}.PDF
    - PyMuPDF 提取文本并更新数据库
    """
    init_db()
    db = get_db()

    rows = db.execute("""
        SELECT id, url, publish_time, company_name
        FROM news_articles
        WHERE article_type LIKE 'cninfo%'
        AND (full_content IS NULL OR full_content = '')
        ORDER BY publish_time DESC
    """).fetchall()

    if not rows:
        log.info("[CNPDF] All articles already have content")
        return 0

    log.info("[CNPDF] %d articles need content backfill", len(rows))

    if limit > 0:
        rows = rows[:limit]

    total = 0
    for i, row in enumerate(rows):
        db_id, url, pub_time, company = row

        # 解析 announcementId
        m = re.search(r"announcementId=(\d+)", url)
        if not m:
            continue
        aid = m.group(1)

        # 提取日期
        date_str = pub_time[:10] if pub_time else ""
        if not date_str:
            continue

        pdf_url = f"{PDF_BASE}/finalpage/{date_str}/{aid}.PDF"
        content = _extract_pdf_text(pdf_url)

        if content:
            with transaction() as tx:
                tx.execute(
                    "UPDATE news_articles SET full_content = ? WHERE id = ?",
                    (content, db_id),
                )
            total += 1

            if (i + 1) % 50 == 0:
                log.info("[CNPDF] Progress: %d/%d updated", total, i + 1)
        else:
            # 标记为无法获取, 避免重复尝试
            with transaction() as tx:
                tx.execute(
                    "UPDATE news_articles SET full_content = '[PDF_UNAVAILABLE]' WHERE id = ?",
                    (db_id,),
                )

        # 礼貌的下载间隔
        time.sleep(random.uniform(0.8, 2.0))

    log.info("[CNPDF] Backfill complete: %d/%d updated", total, len(rows))
    return total
