"""
证券时报 (stcn.com) 新闻爬虫。

来源：LightQuant dataset_construction/news_scraper.py，已适配 SentiPulse 路径与 CSMD 输出格式。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

try:
    from bs4 import BeautifulSoup
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
except ImportError as e:
    raise ImportError(
        "新闻爬虫缺少依赖，请在当前环境安装：\n"
        "  pip install beautifulsoup4 selenium\n"
        "或：pip install -r requirements.txt"
    ) from e

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theory.data_crawler.news_export import export_json_to_csmd_daily
from theory.data_crawler.stock_registry import load_stock_list
from theory.shared.paths import CSMD_RAW_DIR

# 默认缓存目录（未指定 --output-dir 时）
CRAWLER_CACHE = Path(__file__).parent / "_cache"
DEFAULT_NEWS_LINK_DIR = CRAWLER_CACHE / "news_link"
DEFAULT_RAW_NEWS_DIR = CRAWLER_CACHE / "news_raw"


def resolve_output_dirs(output_dir: Optional[str | Path] = None) -> dict:
    """
    解析输出目录。

    指定 output_dir 时结构为：
      <output_dir>/news_link/*.json
      <output_dir>/news_raw/*.json
      <output_dir>/news/<股票名>/<日期>.csv
    未指定时：JSON 在 theory/data_crawler/_cache/，CSV 在 data/processed/CSMD50/news/
    """
    if output_dir:
        root = Path(output_dir).expanduser()
        if not root.is_absolute():
            root = (ROOT / root).resolve()
    else:
        root = None

    if root:
        return {
            "root": root,
            "news_link": root / "news_link",
            "news_raw": root / "news_raw",
            "news_csv": root / "news",
        }
    return {
        "root": CRAWLER_CACHE,
        "news_link": DEFAULT_NEWS_LINK_DIR,
        "news_raw": DEFAULT_RAW_NEWS_DIR,
        "news_csv": CSMD_RAW_DIR / "news",
    }

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"},
]


def _log(msg: str) -> None:
    print(msg, flush=True)


def _chrome_options(headless: bool = True) -> Options:
    opts = Options()
    opts.add_argument(f"user-agent={random.choice(HEADERS_LIST)['User-Agent']}")
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.page_load_strategy = "eager"
    return opts


def _install_hint() -> str:
    mac = sys.platform == "darwin"
    lines = ["本机未检测到可用的 Chrome + chromedriver。请任选一种方式："]
    if mac:
        lines += [
            "  【Mac】安装 Google Chrome 浏览器后执行：",
            "    brew install chromedriver",
            "    python run.py crawl-news ... \\",
            "      --chrome-binary '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \\",
            "      --chromedriver $(which chromedriver)",
        ]
    lines += [
        "  【Linux/Conda】",
        "    conda install -c conda-forge chromium chromedriver -y",
        "  【或继续用已有数据】",
        "    python run.py setup-data --rebuild  # 从 LightQuant 复制新闻",
    ]
    return "\n".join(lines)


def _mac_chrome_candidates() -> list:
    return [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    ]


def _resolve_chrome_paths(
    chrome_binary: Optional[str] = None,
    chromedriver_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Service]]:
    chrome_binary = (
        chrome_binary
        or os.environ.get("CHROME_BIN")
        or os.environ.get("CHROMIUM_BIN")
        or os.environ.get("GOOGLE_CHROME_BIN")
    )
    chromedriver_path = chromedriver_path or os.environ.get("CHROMEDRIVER_PATH")

    if not chrome_binary:
        for name in (
            "google-chrome-stable",
            "google-chrome",
            "chromium",
            "chromium-browser",
            "chrome",
        ):
            found = shutil.which(name)
            if found:
                chrome_binary = found
                break
        if not chrome_binary:
            for p in _mac_chrome_candidates():
                if Path(p).is_file():
                    chrome_binary = p
                    break

    if not chromedriver_path:
        chromedriver_path = shutil.which("chromedriver")
    if not chromedriver_path:
        for p in (
            "/opt/homebrew/bin/chromedriver",
            "/usr/local/bin/chromedriver",
        ):
            if Path(p).is_file():
                chromedriver_path = p
                break

    service = None
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
    else:
        # 网络不佳时 webdriver-manager 常失败；有 Chrome 时仍尝试 Selenium 自带管理器
        _log("[Chrome] 未找到 chromedriver，尝试在线下载（需联网）...")
        try:
            from webdriver_manager.chrome import ChromeDriverManager

            service = Service(ChromeDriverManager().install())
            _log("[Chrome] webdriver-manager 已配置 chromedriver")
        except ImportError:
            _log("[Chrome] 未安装 webdriver-manager，将尝试 Selenium 自带驱动管理")
        except Exception as e:
            _log(f"[Chrome] webdriver-manager 失败: {e}")
            _log("[Chrome] 将尝试 Selenium 自带驱动管理（需已安装 Google Chrome）")

    return chrome_binary, service


def _create_driver(
    headless: bool = True,
    chrome_binary: Optional[str] = None,
    chromedriver_path: Optional[str] = None,
):
    _log("[Chrome] 正在启动 WebDriver...")
    opts = _chrome_options(headless)
    browser, service = _resolve_chrome_paths(chrome_binary, chromedriver_path)

    if browser:
        opts.binary_location = browser
        _log(f"[Chrome] 浏览器: {browser}")
    else:
        _log("[Chrome] 警告: 未找到 Chromium/Chrome，启动可能失败")

    if service and getattr(service, "path", None):
        _log(f"[Chrome] driver: {service.path}")

    try:
        if service:
            driver = webdriver.Chrome(service=service, options=opts)
        else:
            driver = webdriver.Chrome(options=opts)
    except Exception as e:
        err = str(e)
        extra = ""
        if "-9" in err or "unexpectedly exited" in err:
            extra = (
                "\n【macOS 常见修复】chromedriver 被系统终止 (exit -9)：\n"
                "  1) 解除隔离: xattr -d com.apple.quarantine \"$(which chromedriver)\"\n"
                "  2) 测试: chromedriver --version  （应能正常输出版本号）\n"
                "  3) 版本对齐: Chrome 设置→关于→核对主版本号，执行 brew upgrade chromedriver\n"
                "  4) 仍失败可试: python run.py crawl-news ... --no-headless\n"
            )
        if browser and chromedriver_path:
            raise RuntimeError(
                f"已找到 Chrome 与 chromedriver，但启动失败。{extra}\n原始错误: {e}"
            ) from e
        raise RuntimeError(_install_hint() + extra + f"\n原始错误: {e}") from e

    driver.set_page_load_timeout(90)
    driver.set_script_timeout(30)
    _log("[Chrome] 启动成功")
    return driver


def get_article_links(
    slug: str,
    ticker_name: str,
    max_scroll_rounds: int = 30,
    headless: bool = True,
    news_link_dir: Optional[Path] = None,
    chrome_binary: Optional[str] = None,
    chromedriver_path: Optional[str] = None,
) -> list:
    url = (
        "https://stcn.com/article/search.html"
        f"?search_type=news&keyword={ticker_name}&uncertainty=1&sorter=time"
    )
    _log(f"[{ticker_name}] 步骤1: 打开搜索页（最多滚动 {max_scroll_rounds} 次）")
    _log(f"  URL: {url}")

    driver = _create_driver(headless, chrome_binary, chromedriver_path)
    try:
        _log(f"[{ticker_name}] 正在加载页面...")
        driver.get(url)
        time.sleep(3)
        _log(f"[{ticker_name}] 页面已加载，开始滚动...")

        last_height = driver.execute_script("return document.body.scrollHeight")
        count = 0
        retries = 0
        while count < max_scroll_rounds:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                retries += 1
                _log(f"[{ticker_name}] 滚动 {count}/{max_scroll_rounds}，页面高度未变 ({retries}/3)")
                if retries >= 3:
                    break
            else:
                count += 1
                retries = 0
                last_height = new_height
                if count % 3 == 0 or count == 1:
                    _log(f"[{ticker_name}] 滚动进度 {count}/{max_scroll_rounds}")

        _log(f"[{ticker_name}] 解析链接列表...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        article_links = []
        base_url = "https://www.stcn.com/"
        for div in soup.find_all("div", class_="tt"):
            a_tag = div.find("a", href=True)
            if a_tag and "article" in a_tag["href"]:
                article_links.append(base_url + a_tag["href"])

        # 去重保序
        seen = set()
        unique = []
        for link in article_links:
            if link not in seen:
                seen.add(link)
                unique.append(link)

        link_dir = news_link_dir or DEFAULT_NEWS_LINK_DIR
        link_dir.mkdir(parents=True, exist_ok=True)
        out = link_dir / f"{slug}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(unique, f, ensure_ascii=False, indent=2)
        _log(f"[{ticker_name}] 链接数: {len(unique)} -> {out}")
        return unique
    finally:
        driver.quit()
        _log(f"[{ticker_name}] 步骤1 完成，已关闭浏览器")


def fetch_news(
    slug: str,
    ticker_name: str,
    max_articles: Optional[int] = None,
    headless: bool = True,
    news_link_dir: Optional[Path] = None,
    news_raw_dir: Optional[Path] = None,
    chrome_binary: Optional[str] = None,
    chromedriver_path: Optional[str] = None,
) -> Path:
    link_dir = news_link_dir or DEFAULT_NEWS_LINK_DIR
    raw_dir = news_raw_dir or DEFAULT_RAW_NEWS_DIR
    link_file = link_dir / f"{slug}.json"
    if not link_file.exists():
        raise FileNotFoundError(f"请先获取链接: {link_file}")

    with open(link_file, encoding="utf-8") as f:
        article_links = json.load(f)
    if max_articles:
        article_links = article_links[: max_articles]

    all_news = []
    consecutive_failures = 0
    raw_dir.mkdir(parents=True, exist_ok=True)
    total = len(article_links)

    _log(f"[{ticker_name}] 步骤2: 抓取正文，共 {total} 篇")
    driver = _create_driver(headless, chrome_binary, chromedriver_path)
    try:
        for i, article_link in enumerate(article_links, 1):
            try:
                if i % 120 == 0 and i > 1:
                    time.sleep(10)
                _log(f"[{ticker_name}] {i}/{total}: {article_link[:90]}...")
                driver.get(article_link)
                time.sleep(1.2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                detail_content = soup.find("div", class_="detail-content")
                if not detail_content:
                    raise ValueError("未找到 detail-content（网站结构可能已变）")
                for a_tag in detail_content.find_all("a"):
                    a_tag.replace_with(a_tag.text)
                content = detail_content.get_text(strip=True)
                title_el = soup.find("div", class_="detail-title")
                title = title_el.get_text(strip=True) if title_el else ""
                detail_info = soup.find("div", class_="detail-info")
                time_text = ""
                if detail_info:
                    spans = detail_info.find_all("span")
                    if spans:
                        time_text = spans[-1].get_text(strip=True)
                all_news.append(
                    {"time": time_text, "title": title, "content": content, "link": article_link}
                )
                consecutive_failures = 0
            except Exception as e:
                _log(f"  失败: {e}")
                consecutive_failures += 1
                if consecutive_failures >= 10:
                    _log("连续失败 10 次，停止")
                    break
    finally:
        driver.quit()
        _log(f"[{ticker_name}] 步骤2 完成，已关闭浏览器")

    out = raw_dir / f"{slug}.json"
    if consecutive_failures >= 10 and len(all_news) == 0:
        out = raw_dir / f"{slug}_failed.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)
    _log(f"[{ticker_name}] 完成 {len(all_news)} 篇 -> {out}")
    return out


def _parse_ticker_overrides(
    symbols: Optional[list],
    tickers: Optional[list],
) -> Optional[dict]:
    if not tickers:
        return None
    if not symbols or len(tickers) != len(symbols):
        raise ValueError("--ticker 数量须与 --symbols 一致")
    return dict(zip([s.strip() for s in symbols], [t.strip() for t in tickers]))


def run_crawl(
    symbols: Optional[list] = None,
    max_articles: Optional[int] = 20,
    max_scroll_rounds: int = 15,
    headless: bool = True,
    links_only: bool = False,
    export_csmd: bool = True,
    skip_existing: bool = True,
    output_dir: Optional[str | Path] = None,
    ticker_overrides: Optional[dict] = None,
    chrome_binary: Optional[str] = None,
    chromedriver_path: Optional[str] = None,
) -> Path:
    stocks = load_stock_list(symbols, ticker_overrides=ticker_overrides)
    dirs = resolve_output_dirs(output_dir)
    news_out = dirs["news_csv"]

    _log(f"输出根目录: {dirs['root']}")
    _log(f"  链接: {dirs['news_link']}")
    _log(f"  正文 JSON: {dirs['news_raw']}")
    _log(f"  按日 CSV: {news_out}")

    for ticker, code_name, slug in stocks:
        raw_json = dirs["news_raw"] / f"{slug}.json"
        _log(f"\n========== 开始: {code_name} ({ticker}) ==========")
        if skip_existing and raw_json.exists():
            _log(f"跳过爬取（已有缓存）: {code_name} -> {raw_json}")
        else:
            try:
                get_article_links(
                    slug,
                    code_name,
                    max_scroll_rounds,
                    headless,
                    dirs["news_link"],
                    chrome_binary,
                    chromedriver_path,
                )
                if not links_only:
                    fetch_news(
                        slug,
                        code_name,
                        max_articles,
                        headless,
                        dirs["news_link"],
                        dirs["news_raw"],
                        chrome_binary,
                        chromedriver_path,
                    )
            except Exception as e:
                _log(f"[{code_name}] 爬取失败: {e}")
                import traceback

                traceback.print_exc()
                continue

        if export_csmd and raw_json.exists():
            n = export_json_to_csmd_daily(raw_json, code_name, ticker, news_out)
            _log(f"[{code_name}] 已导出 {n} 条 -> {news_out / code_name}/")

    return dirs["root"]


def main():
    parser = argparse.ArgumentParser(description="证券时报新闻爬虫 -> CSMD 按日 CSV")
    parser.add_argument("--symbols", nargs="+", help="股票中文名，如 贵州茅台")
    parser.add_argument("--max-articles", type=int, default=20, help="每只股票最多抓正文篇数（试跑建议 10~30）")
    parser.add_argument("--max-scroll", type=int, default=15, help="列表页滚动次数（越大链接越多）")
    parser.add_argument("--links-only", action="store_true", help="只抓链接列表")
    parser.add_argument("--no-export", action="store_true", help="不写入 data/processed/CSMD50/news")
    parser.add_argument("--no-headless", action="store_true", help="显示浏览器窗口（调试用）")
    parser.add_argument("--force", action="store_true", help="忽略已有缓存重新爬")
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="输出根目录（其下自动创建 news_link/ news_raw/ news/）",
    )
    parser.add_argument(
        "--ticker",
        nargs="+",
        help="手动指定代码，与 --symbols 一一对应，如 sh.600519",
    )
    parser.add_argument("--chrome-binary", default=None, help="Chromium/Chrome 可执行文件路径")
    parser.add_argument("--chromedriver", default=None, help="chromedriver 可执行文件路径")
    args = parser.parse_args()

    out_root = run_crawl(
        symbols=args.symbols,
        max_articles=args.max_articles,
        max_scroll_rounds=args.max_scroll,
        headless=not args.no_headless,
        links_only=args.links_only,
        export_csmd=not args.no_export,
        skip_existing=not args.force,
        output_dir=args.output_dir,
        ticker_overrides=_parse_ticker_overrides(args.symbols, args.ticker),
        chrome_binary=args.chrome_binary,
        chromedriver_path=args.chromedriver,
    )
    if not args.no_export:
        if args.output_dir:
            print(f"\n已写入: {out_root}")
            print("若作为项目数据使用，可将 news/ 复制到 data/processed/CSMD50/ 后执行 setup-data --rebuild")
        else:
            print("\n下一步: python run.py setup-data --rebuild")


if __name__ == "__main__":
    main()
