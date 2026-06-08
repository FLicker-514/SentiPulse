"""
stcn.com search crawler using Playwright (real browser + manual captcha).

Usage:
    uv run python news/stcn_scripts/stcn_playwright_crawler.py "keyword" "company"
    uv run python news/stcn_scripts/stcn_playwright_crawler.py   # batch all 10
"""

import os, re, sys, time, random, logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from database import init_db, insert_news_rows, get_news_urls, get_db
from config import STOCKS

log = logging.getLogger("sentipulse")
STOP_DATE = "2025-01-01"


def setup_logger():
    from logging.handlers import RotatingFileHandler
    logger = logging.getLogger("sentipulse")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    os.makedirs("logs", exist_ok=True)
    fh = RotatingFileHandler("logs/stcn_playwright.log", maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    return logger


def parse_api_html(html: str, company_name: str, fetched_urls: set[str]):
    """Parse <li> HTML from search_data.html API response.
    All text extracted from li.get_text() — no element-level checks.
    Returns (articles, oldest_date_str).
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    all_lis = soup.find_all("li")
    log.info("  PARSE | %d <li> in %d chars", len(all_lis), len(html))

    articles = []
    all_dates = []  # collect ALL dates, even from filtered items
    skip_pdf = 0
    skip_stock = 0
    skip_dup = 0
    skip_no_date = 0
    skip_short_text = 0
    skip_no_source = 0

    for li in all_lis:
        try:
            # Skip non-article types by class
            li_class = " ".join(li.get("class", []))
            if "pdf" in li_class:
                skip_pdf += 1
                text = li.get_text(" ", strip=True)
                m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                if m:
                    all_dates.append(m.group(1))
                continue
            if "stock" in li_class:
                skip_stock += 1
                continue

            # Must have /article/detail/ link
            link = li.find("a", href=re.compile(r"/article/detail/"))
            if not link:
                continue

            href = link.get("href", "")
            url = "https://stcn.com" + href if href.startswith("/") else href
            if url in fetched_urls:
                skip_dup += 1
                continue

            # Extract everything from text
            title = (link.get("title") or link.get_text(strip=True)).strip()
            text = li.get_text(" ", strip=True)

            # Date: collect even if we later skip
            publish_time = ""
            m_full = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", text)
            m_short = re.search(r"(?<!\d)(\d{2}-\d{2}\s+\d{2}:\d{2})", text)
            if m_full:
                publish_time = m_full.group(1)
                all_dates.append(m_full.group(1)[:10])
            elif m_short:
                publish_time = "2026-" + m_short.group(1)
                all_dates.append("2026-" + m_short.group(1)[:5])
            else:
                skip_no_date += 1
                log.info("  PARSE | SKIP no-date: %s", title[:50])
                continue

            # Body = full text minus title and date
            body = text
            for pat in [re.escape(title), re.escape(publish_time),
                        r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}",
                        r"\d{2}-\d{2}\s+\d{2}:\d{2}"]:
                body = re.sub(pat, "", body).strip()

            # Skip if body too short (video/gallery have no descriptive text)
            if len(body) < 15:
                skip_short_text += 1
                log.info("  PARSE | SKIP short-text(%d): %s | %s", len(body), title[:50], url[:80])
                continue

            # Source from text — must match one of these, else skip
            source = ""
            for src_kw in ["证券时报·e公司", "证券时报网", "证券时报", "人民财讯",
                           "第一财经", "券商中国", "数据宝", "e公司"]:
                if src_kw in text:
                    source = src_kw
                    break
            if not source:
                skip_no_source += 1
                log.info("  PARSE | SKIP no-source: %s | %s", title[:50], url[:80])
                continue

            articles.append({
                "company_name": company_name,
                "search_keyword": "stcn_playwright",
                "title": title,
                "url": url,
                "publish_time": publish_time.strip(),
                "source": source,
                "excerpt": body[:500],
                "tags": "",
                "article_type": "stcn_search",
                "full_content": "",
            })
            fetched_urls.add(url)
            log.info("  PARSE | KEEP[%d]: %s | %s | %s | body=%d",
                     len(articles), publish_time, source, title[:50], len(body))
        except Exception as e:
            log.warning("  PARSE | EXCEPTION: %s", e)
            continue

    oldest = min(all_dates) if all_dates else None
    log.info("  PARSE | RESULT: kept=%d all_dates=%d skip(pdf=%d stock=%d dup=%d no_date=%d short=%d no_src=%d) oldest=%s",
             len(articles), len(all_dates), skip_pdf, skip_stock, skip_dup, skip_no_date, skip_short_text, skip_no_source, oldest)
    return articles, oldest


def fetch_article_detail(page, url: str) -> str:
    log.info("  DETAIL | %s", url[:90])
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)
        for sel in [
            ".article-content", ".detail-content", ".news-content",
            "article", ".article-body", ".content", "#article-content",
        ]:
            try:
                el = page.locator(sel)
                if el.count() > 0:
                    content = el.first.inner_text()
                    if len(content) > 100:
                        log.info("  DETAIL | OK selector='%s' len=%d", sel, len(content))
                        return content[:5000]
            except Exception:
                pass
        try:
            content = page.locator("body").inner_text()[:5000]
            log.info("  DETAIL | fallback body len=%d", len(content))
            return content
        except Exception:
            log.warning("  DETAIL | body fallback failed")
            return ""
    except Exception as e:
        log.warning("  DETAIL | error: %s", e)
        return ""


def crawl_stcn(keyword: str, company_name: str, max_pages: int = 500) -> int:
    init_db()
    fetched_urls = get_news_urls()
    log.info("START: keyword=%s company=%s already_fetched=%d", keyword, company_name, len(fetched_urls))
    total_new = 0

    with sync_playwright() as p:
        log.info("BROWSER: launching...")
        browser = p.chromium.launch(headless=False)
        log.info("BROWSER: version=%s", browser.version)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
            locale="zh-CN",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        data_ready = False
        should_stop = False
        rate_limited = False
        page_num = 0

        def on_response(response):
            nonlocal rate_limited, data_ready, should_stop, page_num, total_new

            if "search_data.html" not in response.url or response.status != 200:
                return

            log.info("API | url=%s", response.url[:120])

            try:
                data = response.json()
            except Exception as e:
                log.warning("API | json error: %s", e)
                return

            state = data.get("state")
            msg = data.get("msg", "")
            log.info("API | state=%s msg=%s", state, msg)

            if state == 0:
                if "频繁" in msg:
                    rate_limited = True
                    log.warning("API | RATE-LIMITED")
                else:
                    log.info("API | state=0 (captcha?)")
                return

            # data["data"] is always a string (the HTML)
            html_data = data.get("data", "")
            if not isinstance(html_data, str) or len(html_data) <= 50:
                log.info("API | data field missing/too-short (type=%s len=%d)",
                         type(html_data).__name__, len(html_data) if isinstance(html_data, str) else -1)
                return

            if html_data.strip().startswith("{"):
                log.info("API | html_data is nested JSON, skip")
                return

            log.info("API | parsing %d chars...", len(html_data))

            # Parse — ALWAYS get oldest date, even if 0 articles kept
            articles, oldest = parse_api_html(html_data, company_name, fetched_urls)
            log.info("API | articles=%d oldest=%s", len(articles), oldest)

            # Check stop BEFORE inserting (date comes from all items, not just kept ones)
            if oldest and oldest < STOP_DATE:
                log.info("API | STOP: oldest=%s < %s", oldest, STOP_DATE)
                should_stop = True

            if articles:
                inserted = 0
                for art in articles:
                    inserted += insert_news_rows([art])
                total_new += inserted
                log.info("API | inserted %d/%d, total=%d", inserted, len(articles), total_new)
            else:
                log.info("API | 0 articles kept (all filtered)")

            data_ready = True
            page_num += 1
            log.info("API | PAGE %d DONE | total=%d should_stop=%s", page_num, total_new, should_stop)

        page.on("response", on_response)

        search_url = f"https://stcn.com/article/search.html?keyword={keyword}"
        log.info("PAGE | goto: %s", search_url)
        page.goto(search_url, timeout=30000)
        log.info("PAGE | loaded: %s", page.url[:120])

        # --- Initial scroll ---
        log.info("INIT | waiting for first data...")
        time.sleep(3)
        t0 = time.time()
        loop_i = 0
        while time.time() - t0 < 600 and not data_ready:
            loop_i += 1
            if rate_limited:
                wait_sec = random.uniform(30, 180)
                log.warning("INIT | rate-limited, wait %.0fs", wait_sec)
                page.evaluate("window.scrollBy(0, -600)")
                time.sleep(wait_sec)
                rate_limited = False
                page.evaluate("window.scrollTo(0, 999999)")
                t0 = time.time()
                continue
            page.evaluate("window.scrollTo(0, 999999)")
            if loop_i % 5 == 1:
                log.info("INIT | scroll #%d elapsed=%.0fs...", loop_i, time.time() - t0)
            time.sleep(2)

        if not data_ready:
            log.error("INIT | timeout, no data")
            browser.close()
            return 0

        log.info("INIT | data ready after %.0fs", time.time() - t0)

        # --- Main scroll ---
        while page_num < max_pages and not should_stop:
            try:
                if page.locator(".no-more").is_visible(timeout=1000):
                    log.info("LOOP | .no-more visible")
                    break
            except Exception:
                pass

            delay = random.uniform(2.5, 4.0)
            log.info("LOOP | sleep %.1fs, scroll down", delay)
            time.sleep(delay)
            page.evaluate("window.scrollTo(0, 999999)")
            time.sleep(2)

            last_page = page_num
            w0 = time.time()
            while time.time() - w0 < 20 and page_num == last_page and not should_stop:
                if rate_limited:
                    wait_sec = random.uniform(30, 180)
                    log.warning("LOOP | rate-limited, wait %.0fs", wait_sec)
                    page.evaluate("window.scrollBy(0, -600)")
                    time.sleep(wait_sec)
                    rate_limited = False
                    page.evaluate("window.scrollTo(0, 999999)")
                    time.sleep(2)
                    w0 = time.time()
                    last_page = page_num
                elif page.locator(".no-more").is_visible():
                    log.info("LOOP | .no-more visible (wait)")
                    break
                time.sleep(1)

            if page_num == last_page and not rate_limited:
                log.info("LOOP | no response for 20s")
                break

        log.info("SCROLL | done: %d pages, %d articles, should_stop=%s", page_num, total_new, should_stop)

        # --- Detail fetch ---
        to_fetch = get_db().execute(
            "SELECT id, url FROM news_articles "
            "WHERE article_type='stcn_search' AND (full_content IS NULL OR full_content='') "
            "ORDER BY id"
        ).fetchall()
        log.info("DETAIL | %d articles need content", len(to_fetch))

        ok = skip = 0
        for db_id, detail_url in to_fetch:
            content = fetch_article_detail(page, detail_url)
            if content and len(content) > 50:
                get_db().execute("UPDATE news_articles SET full_content = ? WHERE id = ?", (content, db_id))
                get_db().commit()
                ok += 1
            else:
                log.info("  DETAIL | SKIP id=%d (content=%d chars)", db_id, len(content) if content else 0)
                skip += 1
            time.sleep(random.uniform(1.0, 2.5))
            if (ok + skip) % 20 == 0:
                log.info("DETAIL | progress: %d/%d ok=%d skip=%d", ok + skip, len(to_fetch), ok, skip)

        log.info("DETAIL | done: %d ok, %d skip, %d total", ok, skip, len(to_fetch))
        browser.close()

    log.info("DONE: %s -> %d new", company_name, total_new)
    return total_new


def main():
    setup_logger()

    if len(sys.argv) >= 3:
        target, company = sys.argv[1], sys.argv[2]
        crawl_stcn(target, company)
    elif len(sys.argv) >= 2:
        target = sys.argv[1]
        company = target
        for name, code in STOCKS.items():
            if name in target or code in target:
                company = name
                break
        crawl_stcn(target, company)
    else:
        for i, (name, code) in enumerate(STOCKS.items()):
            log.info("=" * 50)
            log.info("[%d/%d] %s (%s)", i + 1, len(STOCKS), name, code)
            log.info("=" * 50)
            n1 = crawl_stcn(name, name)
            time.sleep(random.uniform(5, 10))
            n2 = crawl_stcn(code, name)
            log.info("%s: %d", name, n1 + n2)
            if i < len(STOCKS) - 1:
                time.sleep(random.uniform(30, 60))
        log.info("BATCH DONE")


if __name__ == "__main__":
    main()
