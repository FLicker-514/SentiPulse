from pathlib import Path

from theory.shared.paths import CSMD_RAW_DIR

DEFAULT_SYMBOLS = ["贵州茅台", "金山办公", "海尔智家", "恒瑞医药"]


def list_symbols_from_data(price_dir: Path) -> list:
    if not price_dir.is_dir():
        return DEFAULT_SYMBOLS.copy()
    names = sorted(p.stem for p in price_dir.glob("*.csv"))
    return names if names else DEFAULT_SYMBOLS.copy()


def default_price_dir() -> Path:
    return CSMD_RAW_DIR / "price"
