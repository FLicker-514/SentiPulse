"""
巨潮资讯 (Cninfo) 公司公告数据采集

数据来源: 中国证监会指定信息披露平台 — 巨潮资讯网 (cninfo.com.cn)

特点:
- 免费公开, 无需认证
- 支持日期范围过滤 (sdate/edate)
- 支持公司名称/代码搜索
- 覆盖所有 A 股上市公司的法定披露公告
- 历史数据可追溯多年

公告类型包括:
- 董事会/监事会/股东大会决议
- 定期报告 (年报、半年报、季报)
- 重大合同、资产重组、股权变动
- 回购、分红、增发、配股
- 业绩预告、业绩快报
"""

import random
import re
import time
import logging
from urllib.parse import urljoin, quote

import requests

from config import (
    STOCKS,
    USER_AGENTS,
    NEWS_DELAY_MIN,
    NEWS_DELAY_MAX,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF,
    START_DATE,
    END_DATE,
)
from database import init_db, insert_news_rows, get_news_urls

log = logging.getLogger("sentipulse")

CNINFO_SEARCH_URL = "http://www.cninfo.com.cn/new/fulltextSearch/full"
CNINFO_DETAIL_URL = "http://www.cninfo.com.cn/new/announcement/detail"
CNINFO_BASE_URL = "http://www.cninfo.com.cn"


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _headers(referer: str = CNINFO_BASE_URL) -> dict:
    return {
        "User-Agent": _random_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
        "Connection": "keep-alive",
    }


def _fetch_cninfo_page(searchkey: str, page_num: int, sdate: str, edate: str,
                       page_size: int = 30) -> dict | None:
    """从 Cninfo 获取一页公告搜索结果"""
    params = {
        "searchkey": searchkey,
        "sdate": sdate,
        "edate": edate,
        "isfulltext": "false",
        "sortName": "pubdate",
        "sortType": "desc",
        "pageNum": str(page_num),
        "pageSize": str(page_size),
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                CNINFO_SEARCH_URL,
                params=params,
                headers=_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            resp.encoding = "utf-8"

            if resp.status_code == 200:
                return resp.json()
            log.warning("[CNINFO] HTTP %d for key=%s page=%d (attempt %d)",
                       resp.status_code, searchkey, page_num, attempt + 1)
        except Exception as e:
            log.warning("[CNINFO] %s (attempt %d/%d)", e, attempt + 1, MAX_RETRIES)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF * (attempt + 1))

    return None


def _parse_announcement(item: dict, company_name: str) -> dict:
    """将 Cninfo 公告转为统一新闻格式"""
    announcement_id = item.get("announcementId", "")
    adjunct_url = item.get("adjunctUrl", "")

    # 构建详情页 URL
    if announcement_id:
        url = f"{CNINFO_DETAIL_URL}?announcementId={announcement_id}"
    elif adjunct_url:
        url = urljoin(CNINFO_BASE_URL, adjunct_url)
    else:
        url = ""

    title = item.get("announcementTitle", "")
    # 清理 HTML 标签
    title = re.sub(r"<[^>]+>", "", title)

    # 时间转换 (Unix 毫秒)
    ts = item.get("announcementTime", 0)
    if ts:
        from datetime import datetime
        publish_time = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
    else:
        publish_time = ""

    # 公告类型
    ann_type = item.get("announcementTypeName", "")

    # 摘要 (从 announcementContent 提取前段)
    content = item.get("announcementContent", "")
    if content:
        content = re.sub(r"<[^>]+>", "", content)
        content = content.replace("&nbsp;", " ").replace("\r\n", " ").replace("\n", " ")
    excerpt = content[:500] if content else ""

    return {
        "company_name": company_name,
        "search_keyword": f"cninfo_{company_name}",
        "title": title,
        "url": url,
        "publish_time": publish_time,
        "source": f"巨潮资讯",
        "excerpt": excerpt,
        "tags": ann_type,
        "article_type": f"cninfo_{ann_type}" if ann_type else "cninfo_announcement",
        "full_content": content[:3000] if content else "",
    }


def _crawl_by_keyword(company_name: str, search_key: str,
                      fetched_urls: set[str],
                      sdate: str, edate: str) -> int:
    """按关键词采集公告, 返回新增条数"""
    total_new = 0
    data = _fetch_cninfo_page(search_key, 1, sdate, edate)
    if not data:
        return 0

    total_pages = data.get("totalpages", 0)
    total_records = data.get("totalAnnouncement", 0)

    if total_records == 0:
        return 0

    log.info("[CNINFO] keyword=%s: %d 条, %d 页", search_key, total_records, total_pages)

    for page in range(1, total_pages + 1):
        if page > 1:
            time.sleep(random.uniform(0.5, 1.0))
            data = _fetch_cninfo_page(search_key, page, sdate, edate)
            if not data:
                break

        for item in data.get("announcements", []):
            row = _parse_announcement(item, company_name)
            if row["url"] and row["url"] not in fetched_urls:
                n = insert_news_rows([row])
                total_new += n
                fetched_urls.add(row["url"])

    return total_new


def crawl_company_announcements(company_name: str, stock_code: str = "",
                                sdate: str = START_DATE,
                                edate: str = END_DATE) -> int:
    """采集单个企业的公告数据 (公司名 + 股票代码双关键词)"""
    log.info("[CNINFO] 开始采集 %s (%s) 的公告 (%s ~ %s)",
             company_name, stock_code, sdate, edate)

    fetched_urls = get_news_urls()
    total_new = 0

    # 1. 按公司名搜索
    total_new += _crawl_by_keyword(company_name, company_name, fetched_urls, sdate, edate)

    # 2. 按股票代码搜索 (补充公司名搜索遗漏的数据)
    if stock_code:
        total_new += _crawl_by_keyword(company_name, stock_code, fetched_urls, sdate, edate)

    log.info("[CNINFO] %s 公告采集完毕: 共新增 %d 条", company_name, total_new)
    return total_new


def crawl_all_announcements() -> dict[str, int]:
    """采集所有目标企业的公告数据"""
    init_db()
    results = {}

    for name, code in STOCKS.items():
        try:
            n = crawl_company_announcements(name, code)
            results[name] = n
        except Exception as e:
            log.error("[CNINFO] %s 公告采集失败: %s", name, e)
            results[name] = 0

        # 企业间休息
        time.sleep(random.uniform(1.0, 2.0))

    return results
