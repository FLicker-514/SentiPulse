"""股票代码表：中文名 <-> baostock code。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from theory.shared.paths import CSMD_RAW_DIR, EXTERNAL_LIGHTQUANT


def _read_csv(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def _slug_from_code(code: str) -> str:
    return code.replace("sh.", "").replace("sz.", "").strip()


def _registry_from_csv_file(path: Path) -> Dict[str, Tuple[str, str, str]]:
    df = _read_csv(path)
    if df is None:
        return {}
    cols = {c.lower(): c for c in df.columns}
    code_col = cols.get("code") or "code"
    name_col = cols.get("code_name") or "code_name"
    mapping = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col]).strip()
        if not code or not name or name == "nan":
            continue
        mapping[name] = (code, name, _slug_from_code(code))
    return mapping


def _registry_from_existing_news() -> Dict[str, Tuple[str, str, str]]:
    """从 data/processed/CSMD50/news/<股票>/*.csv 读取 ticker 列。"""
    news_root = CSMD_RAW_DIR / "news"
    if not news_root.is_dir():
        return {}
    mapping = {}
    for sym_dir in sorted(news_root.iterdir()):
        if not sym_dir.is_dir():
            continue
        name = sym_dir.name
        for csv_path in sorted(sym_dir.glob("*.csv")):
            try:
                df = pd.read_csv(csv_path, encoding="utf-8-sig", nrows=5)
            except Exception:
                continue
            if "ticker" not in df.columns:
                continue
            code = str(df["ticker"].dropna().iloc[0]).strip()
            if code:
                mapping[name] = (code, name, _slug_from_code(code))
                break
    return mapping


def load_stock_list(
    symbols: Optional[List[str]] = None,
    ticker_overrides: Optional[Dict[str, str]] = None,
) -> List[Tuple[str, str, str]]:
    """
    返回 [(ticker, code_name, slug), ...]
    ticker 如 sh.600519；slug 用于 json 缓存文件名（用 code 中的数字部分）。
    ticker_overrides: { "贵州茅台": "sh.600519" }，无 CSMD50.csv 时可用。
    """
    registry = load_ticker_map()
    overrides = ticker_overrides or {}

    if symbols:
        out = []
        for s in symbols:
            s = s.strip()
            if s in overrides:
                code = overrides[s].strip()
                out.append((code, s, _slug_from_code(code)))
            elif s in registry:
                out.append(registry[s])
            else:
                raise ValueError(
                    f"未找到股票「{s}」的代码。请任选其一：\n"
                    f"  1) 复制 CSMD50.csv 到 theory/data_crawler/\n"
                    f"  2) 确保 data/processed/CSMD50/news/{s}/ 下已有带 ticker 列的 CSV\n"
                    f"  3) 使用 --ticker sh.600519 手动指定"
                )
        return out

    price_dir = CSMD_RAW_DIR / "price"
    if price_dir.is_dir():
        names = sorted(p.stem for p in price_dir.glob("*.csv"))
        return [registry[n] for n in names if n in registry]

    return list(registry.values())


def load_ticker_map() -> Dict[str, Tuple[str, str, str]]:
    """key: 中文名 code_name；多来源合并。"""
    mapping: Dict[str, Tuple[str, str, str]] = {}

    for path in (
        Path(__file__).parent / "CSMD50.csv",
        EXTERNAL_LIGHTQUANT / "llm_factor" / "CSMD50.csv",
    ):
        mapping.update(_registry_from_csv_file(path))

    mapping.update(_registry_from_existing_news())

    if not mapping:
        raise FileNotFoundError(
            "未找到任何股票代码映射。请任选其一：\n"
            "  cp ../LightQuant/llm_factor/CSMD50.csv theory/data_crawler/\n"
            "  或先保证 data/processed/CSMD50/news/<股票名>/*.csv 含 ticker 列\n"
            "  或使用: python run.py crawl-news --symbols 贵州茅台 --ticker sh.600519"
        )
    return mapping
