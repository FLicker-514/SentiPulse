"""
新闻数据采集: 东方财富 (Eastmoney) 搜索 API

数据来源:
- 主接口: search-api-web.eastmoney.com/search/jsonp
- 数据聚合自 证券时报、中国证券报、上海证券报、证券日报 等权威财经媒体

特点:
- 无需认证, JSON 格式返回
- 每页最多 50 条, 每个搜索约可获取 500+ 条
- 通过搜索 股票代码 + 公司名称 双关键词最大化数据量
"""

import json
import random
import re
import time
import logging

import requests

from config import (
    STOCKS,
    STCN_BASE_URL,
    USER_AGENTS,
    NEWS_DELAY_MIN,
    NEWS_DELAY_MAX,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from database import init_db, insert_news_rows, get_news_urls, upsert_progress

log = logging.getLogger("sentipulse")

EM_SEARCH_URL = "https://search-api-web.eastmoney.com/search/jsonp"


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _em_headers(keyword: str) -> dict:
    # URL-encode keyword for Referer (Chinese chars not valid in HTTP headers)
    from urllib.parse import quote
    return {
        "User-Agent": _random_ua(),
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": f"https://so.eastmoney.com/news/s?keyword={quote(keyword)}",
        "Connection": "keep-alive",
    }


def _fetch_em_page(keyword: str, page_index: int, page_size: int = 50) -> list[dict]:
    """从东方财富 API 获取一页搜索结果"""
    inner = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": "date",
                "pageIndex": page_index,
                "pageSize": page_size,
                "preTag": "<em>",
                "postTag": "</em>",
            }
        },
    }
    params = {
        "cb": "jQuery_test",
        "param": json.dumps(inner, ensure_ascii=False),
        "_": str(int(time.time() * 1000)),
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(
                EM_SEARCH_URL,
                params=params,
                headers=_em_headers(keyword),
                timeout=REQUEST_TIMEOUT,
            )
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                log.warning("[NEWS] HTTP %d for keyword=%s page=%d (attempt %d)",
                           resp.status_code, keyword, page_index, attempt + 1)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_BACKOFF * (attempt + 1))
                continue

            # 解析 JSONP
            text = resp.text
            m = re.search(r"\((.*)\)\s*$", text, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
            else:
                data = json.loads(text)

            articles = data.get("result", {}).get("cmsArticleWebOld", [])
            if not isinstance(articles, list):
                return []
            return articles

        except Exception as e:
            log.warning("[NEWS] 请求异常 keyword=%s page=%d: %s (attempt %d/%d)",
                       keyword, page_index, e, attempt + 1, MAX_RETRIES)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF * (attempt + 1))

    return []


def _parse_em_article(item: dict, company_name: str, keyword: str) -> dict | None:
    """将 API 返回的单条记录转为数据库格式"""
    code = item.get("code", "")
    if not code:
        return None

    url = f"http://finance.eastmoney.com/a/{code}.html"
    title = item.get("title", "")
    content = item.get("content", "")
    publish_time = item.get("date", "")
    source = item.get("mediaName", "")

    # 清洗 HTML 标签 (文章标题和内容中可能有 <em> 高亮标签)
    title = re.sub(r"<[^>]+>", "", title)
    content = re.sub(r"<[^>]+>", "", content)
    content = content.replace("　", " ").replace("\r\n", " ")

    return {
        "company_name": company_name,
        "search_keyword": keyword,
        "title": title,
        "url": url,
        "publish_time": publish_time,
        "source": source,
        "excerpt": content[:500] if content else "",
        "tags": "",
        "article_type": "em_search",
        "full_content": content[:2000] if content else "",
    }


def search_em_keyword(company_name: str, keyword: str, fetched_urls: set[str],
                      max_pages: int = 15) -> int:
    """按关键词搜索东方财富新闻, 逐页采集直到无数据"""
    total_new = 0
    consecutive_empty = 0
    oldest_date_seen = "9999"
    stale_pages = 0

    for page in range(1, max_pages + 1):
        raw_articles = _fetch_em_page(keyword, page)

        if not raw_articles:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                log.info("[NEWS] %s / keyword=%s: 连续 %d 页无数据, 停止 (共 %d 页)",
                         company_name, keyword, consecutive_empty, page - 1)
                break
            continue

        consecutive_empty = 0
        rows = []
        for item in raw_articles:
            row = _parse_em_article(item, company_name, keyword)
            if row and row["url"] not in fetched_urls:
                rows.append(row)
                fetched_urls.add(row["url"])

        if rows:
            n = insert_news_rows(rows)
            total_new += n

        first_date = raw_articles[0].get("date", "?")
        last_date = raw_articles[-1].get("date", "?")
        log.info("[NEWS] %s / keyword=%s page=%d: 获取 %d 条, 新增 %d 条 (%s ~ %s)",
                 company_name, keyword, page, len(raw_articles),
                 len(rows) if rows else 0, last_date[:10], first_date[:10])

        # 检查日期是否在向前推进
        page_min_date = min(
            (a.get("date", "9999")[:10] for a in raw_articles),
            default="9999",
        )
        if page_min_date < oldest_date_seen:
            oldest_date_seen = page_min_date
            stale_pages = 0
        else:
            stale_pages += 1

        # 最后一页通常不满 50 条; 日期 3 页不前进也停止
        if len(raw_articles) < 50:
            log.info("[NEWS] %s / keyword=%s: 最后页不足 %d 条, 结束",
                     company_name, keyword, len(raw_articles))
            break

        if stale_pages >= 3:
            log.info("[NEWS] %s / keyword=%s: 日期 %d 页未推进 (stuck at %s), 停止",
                     company_name, keyword, stale_pages, oldest_date_seen)
            break

        time.sleep(random.uniform(NEWS_DELAY_MIN, NEWS_DELAY_MAX))

    return total_new


def crawl_company_news(company_name: str, code: str) -> int:
    """采集单个企业的新闻: 按股票代码 + 公司名称分别搜索"""
    log.info("[NEWS] === 开始采集 %s (%s) 的新闻 ===", company_name, code)

    fetched_urls = get_news_urls()
    total = 0

    # 1. 按股票代码搜索
    total += search_em_keyword(company_name, code, fetched_urls)

    # 2. 按公司名称搜索
    total += search_em_keyword(company_name, company_name, fetched_urls)

    upsert_progress("news", company_name, status="completed", total_items=total)
    return total


def crawl_all_news() -> dict[str, int]:
    """采集所有目标企业的新闻数据"""
    init_db()
    results = {}

    for name, code in STOCKS.items():
        try:
            n = crawl_company_news(name, code)
            results[name] = n
            log.info("[NEWS] %s 新闻采集完成: 共新增 %d 篇", name, n)
        except Exception as e:
            log.error("[NEWS] %s 新闻采集失败: %s", name, e)
            results[name] = 0
            upsert_progress("news", name, status="failed", last_error=str(e))

        # 两个企业之间多休息一下
        time.sleep(random.uniform(NEWS_DELAY_MIN * 2, NEWS_DELAY_MAX * 2))

    return results
