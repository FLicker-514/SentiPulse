"""加载 CSMD 新闻文本供情绪分析。"""

import json
from typing import Optional, Tuple

import requests

from theory.shared.config import Settings
from theory.shared.paths import CSMD_NEWS_JSON


def load_csmd_news(symbol: str) -> str:
    symbol = symbol.strip()
    if not CSMD_NEWS_JSON.exists():
        return f"未找到新闻文件，请先运行 python run.py setup-data"
    with open(CSMD_NEWS_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get(symbol, data.get(symbol.upper(), ""))


def resolve_news_text(
    symbol: str,
    news_text: Optional[str] = None,
    use_api: bool = True,
) -> Tuple[str, str]:
    if news_text and news_text.strip():
        return news_text.strip(), "user"
    if use_api and Settings.NEWS_API_KEY:
        try:
            r = requests.get(
                "https://newsapi.org/v2/everything",
                params={"q": symbol, "apiKey": Settings.NEWS_API_KEY, "pageSize": 3},
                timeout=15,
            )
            r.raise_for_status()
            parts = [
                f"{a.get('title','')}. {a.get('description','')}"
                for a in r.json().get("articles", [])
            ]
            if parts:
                return " ".join(parts), "newsapi"
        except requests.RequestException:
            pass
    body = load_csmd_news(symbol)
    return body, "csmd" if body else "empty"
