"""
证券时报 (stcn.com) 新闻数据采集 — 月度归档页方案

策略:
- stcn.com 的搜索功能有严格的反爬保护 (RSA加密头)
- 但月度归档页面 (/article/list/YYYYMM.html) 是服务端渲染, 可以直接获取
- 每页约 167 篇文章链接, 无法翻页 (分页需要加密头)
- 按月汇总所有文章, 按标题中的企业名称/股票代码过滤匹配
- 匹配后抓取文章详情页获取完整内容

局限性:
- 每月仅能获取第一页 (~167 篇), 非全量
- 对于热门企业, 这 167 篇中通常包含 3-10 篇相关报道
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import random
import re
import time
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

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
from database import init_db, insert_news_rows, get_news_urls

log = logging.getLogger("sentipulse")


def _random_ua() -> str:
    return random.choice(USER_AGENTS)


def _get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": _random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    # 先访问首页获取 cookie
    try:
        s.get(STCN_BASE_URL, timeout=15)
    except Exception:
        pass
    return s


def _fetch_page(session: requests.Session, url: str, params: dict = None) -> str | None:
    """带重试的页面获取"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            log.warning("[STCN] HTTP %d for %s (attempt %d)", resp.status_code, url, attempt + 1)
        except Exception as e:
            log.warning("[STCN] %s (attempt %d/%d)", e, attempt + 1, MAX_RETRIES)

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


def _parse_archive_page(html: str) -> list[dict]:
    """从月度归档页提取所有文章链接"""
    soup = BeautifulSoup(html, "lxml")
    articles = []

    for a in soup.select("a[href*='/article/detail/']"):
        href = a.get("href", "")
        title = a.get("title") or a.get_text(strip=True)
        if not href or not title:
            continue

        url = urljoin(STCN_BASE_URL, href)
        m = re.search(r"/article/detail/(\d+)", href)
        article_id = m.group(1) if m else ""

        articles.append({
            "url": url,
            "title": title,
            "article_id": article_id,
        })

    # 去重 (同一篇文章可能在页面中出现多次)
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique


def _matches_company(title: str, company_name: str, stock_code: str) -> bool:
    """检查文章标题是否与目标企业相关"""
    # 简短名称匹配 (避免全称太长导致的匹配问题)
    short_names = {
        "交通银行": ["交通银行", "交行"],
        "保利发展": ["保利发展", "保利地产", "保利"],
        "国电南瑞": ["国电南瑞", "南瑞"],
        "工商银行": ["工商银行", "工行", "ICBC"],
        "恒瑞医药": ["恒瑞医药", "恒瑞"],
        "海光信息": ["海光信息", "海光"],
        "海天味业": ["海天味业", "海天"],
        "海尔智家": ["海尔智家", "海尔"],
        "贵州茅台": ["贵州茅台", "茅台", "贵州茅台"],
        "金山办公": ["金山办公", "金山", "WPS"],
    }

    keywords = short_names.get(company_name, [company_name])
    keywords.append(stock_code)

    for kw in keywords:
        if kw in title:
            return True
    return False


def _fetch_article_detail(session: requests.Session, url: str) -> dict | None:
    """获取文章详情页, 提取正文和元数据"""
    html = _fetch_page(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")

    # 提取发布时间
    publish_time = ""
    time_elem = (
        soup.find("time")
        or soup.find("span", class_=re.compile(r"time|date|pub", re.I))
        or soup.find("div", class_=re.compile(r"time|date|info", re.I))
    )
    if time_elem:
        publish_time = time_elem.get_text(strip=True)
    if not publish_time:
        # 尝试从 URL 中推断 (部分 stcn 文章URL包含日期)
        m = re.search(r"(\d{4}-\d{2}-\d{2})", soup.get_text()[:2000])
        if m:
            publish_time = m.group(1)

    # 提取来源
    source = "证券时报"
    source_elem = soup.find("span", class_=re.compile(r"source|from|origin", re.I))
    if source_elem:
        source_text = source_elem.get_text(strip=True)
        if source_text:
            source = source_text.replace("来源：", "").replace("来源:", "").strip()

    # 提取正文
    content = ""
    content_elem = (
        soup.find("div", class_=re.compile(r"article-content|detail-content|content", re.I))
        or soup.find("div", id=re.compile(r"content|article", re.I))
        or soup.find("article")
    )
    if content_elem:
        content = content_elem.get_text(strip=True)

    # 提取摘要
    excerpt = content[:500] if content else ""

    # 提取标签
    tag_elems = soup.select("a.tag, span.tag, a[href*='tag']")
    tags = ",".join(t.get_text(strip=True) for t in tag_elems) if tag_elems else ""

    return {
        "publish_time": publish_time,
        "source": source,
        "excerpt": excerpt,
        "tags": tags,
        "full_content": content[:3000] if content else "",
    }


def crawl_stcn_archives(
    start_month: str = "202501",
    end_month: str = "202606",
) -> int:
    """
    从 stcn.com 月度归档页采集新闻:
    - 遍历每个月的归档页
    - 提取所有文章链接
    - 按企业名称过滤匹配
    - 获取匹配文章的详情
    """
    init_db()
    session = _get_session()
    fetched_urls = get_news_urls()
    total_new = 0

    # 生成月份列表
    months = []
    y, m = int(start_month[:4]), int(start_month[4:])
    ey, em = int(end_month[:4]), int(end_month[4:])
    while (y < ey) or (y == ey and m <= em):
        months.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1

    log.info("[STCN] 开始扫描 %d 个月度归档页 (%s ~ %s)",
             len(months), months[0], months[-1])

    archive_articles = {}  # company_name -> [articles from archive page]

    for month_str in months:
        url = f"{STCN_BASE_URL}/article/list/{month_str}.html"
        html = _fetch_page(session, url)

        if not html:
            log.warning("[STCN] 归档页 %s 获取失败", month_str)
            continue

        articles = _parse_archive_page(html)
        log.info("[STCN] %s: 提取 %d 篇文章链接", month_str, len(articles))

        # 按企业过滤
        matched = 0
        for art in articles:
            for company_name, stock_code in STOCKS.items():
                if _matches_company(art["title"], company_name, stock_code):
                    if company_name not in archive_articles:
                        archive_articles[company_name] = []
                    art_copy = art.copy()
                    art_copy["company_name"] = company_name
                    archive_articles[company_name].append(art_copy)
                    matched += 1
                    break  # 一篇文章只归属一个企业

        log.info("[STCN] %s: %d 篇匹配目标企业", month_str, matched)

        time.sleep(random.uniform(1.0, 2.0))

    # 对匹配的文章, 抓取详情页
    log.info("[STCN] 开始抓取 %d 篇匹配文章的详情...",
             sum(len(v) for v in archive_articles.values()))

    for company_name, articles in archive_articles.items():
        for art in articles:
            url = art["url"]
            if url in fetched_urls:
                continue

            detail = _fetch_article_detail(session, url)
            time.sleep(random.uniform(0.5, 1.5))

            row = {
                "company_name": company_name,
                "search_keyword": f"stcn_archive",
                "title": art["title"],
                "url": url,
                "publish_time": detail["publish_time"] if detail else "",
                "source": detail["source"] if detail else "证券时报",
                "excerpt": detail["excerpt"] if detail else "",
                "tags": detail["tags"] if detail else "",
                "article_type": "stcn_archive",
                "full_content": detail["full_content"] if detail else "",
            }

            if row["url"] not in fetched_urls:
                n = insert_news_rows([row])
                total_new += n
                fetched_urls.add(url)
                if n > 0:
                    log.info("[STCN] + %s: %s", company_name, art["title"][:60])

    log.info("[STCN] 归档页采集完毕: 共新增 %d 篇 stcn.com 文章", total_new)
    return total_new
