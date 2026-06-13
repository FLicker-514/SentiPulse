"""SentiPulse 全局路径：所有数据统一在 data/ 目录。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

DEFAULT_DATASET = "CSMD50"

# ---------- 数据根目录 ----------
PROCESSED_DIR = DATA_DIR / "processed"

# 原始 CSMD（价量 + 新闻）：data/processed/CSMD50/
CSMD_RAW_DIR = PROCESSED_DIR / DEFAULT_DATASET

# 清洗后（LSTM / 情绪推理用）
DATASETS_DIR = PROCESSED_DIR / "datasets"
CLEANED_CSV = PROCESSED_DIR / "CSMD_cleaned.csv"
CSMD_NEWS_JSON = PROCESSED_DIR / "csmd_news.json"
SENTIMENT_DAILY_CSV = PROCESSED_DIR / "sentiment_daily.csv"  # FinBERT2-large 日度情感
SENTIMENT_DAILY_BERT_CSV = PROCESSED_DIR / "sentiment_daily_bert.csv"  # 未微调 Bert

# 模型权重
MODELS_DIR = DATA_DIR / "models"
EXTERNAL_MODELS_DIR = ROOT.parent / "models"  # 如 ~/yangzilong/models
FINBERT_DIR = MODELS_DIR / "FinBERT-zh"
FINBERT2_LARGE_DIR = EXTERNAL_MODELS_DIR / "FinBERT2-large"
FINBERT_LARGE_DIR = MODELS_DIR / "FinBERT-large"
BERT_DIR = EXTERNAL_MODELS_DIR / "Bert"
BERT_LOCAL_DIR = MODELS_DIR / "Bert"

# 外部 LightQuant（setup-data 从同级仓库复制时用）
EXTERNAL_LIGHTQUANT = ROOT.parent / "LightQuant"

SEQ_LENGTH = 60
FORECAST_HORIZON = 7

# 默认：2024-01-01 之前训练，2024 年及以后用于预测/回测
DEFAULT_TRAIN_END = "2024-01-01"
DEFAULT_TEST_START = "2024-01-01"

# 预测模式
MODEL_TS_ONLY = "ts-only"
MODEL_FUSION_BERT = "fusion-bert"  # 融合未微调 Bert 情感
MODEL_FUSION = "fusion"  # 融合 FinBERT2-large 情感
FUSION_MODES = (MODEL_FUSION_BERT, MODEL_FUSION)
ALL_TRAIN_MODES = (MODEL_TS_ONLY, MODEL_FUSION_BERT, MODEL_FUSION)


def is_fusion_mode(mode: str) -> bool:
    return mode in FUSION_MODES


def resolve_sentiment_model_dir(variant: str) -> Path:
    """variant: bert | finbert"""
    from theory.shared.config import Settings

    variant = variant.strip().lower()
    if variant not in ("bert", "finbert"):
        raise ValueError(f"未知 sentiment variant: {variant}")

    env_val = Settings.BERT_MODEL_PATH if variant == "bert" else Settings.SENTIMENT_MODEL_PATH
    if env_val and str(env_val).strip():
        p = Path(str(env_val).strip()).expanduser()
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        return p

    candidates = (
        [BERT_LOCAL_DIR, BERT_DIR]
        if variant == "bert"
        else [
            FINBERT2_LARGE_DIR,
            FINBERT_DIR,
            FINBERT_LARGE_DIR,
            EXTERNAL_MODELS_DIR / "FinBERT-zh",
        ]
    )
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def sentiment_csv_path(mode: str) -> Path:
    if mode == MODEL_FUSION_BERT:
        return SENTIMENT_DAILY_BERT_CSV
    if mode == MODEL_FUSION:
        return SENTIMENT_DAILY_CSV
    raise ValueError(f"mode {mode} 不使用日度情感特征")


def sentiment_variant_for_mode(mode: str) -> str:
    if mode == MODEL_FUSION_BERT:
        return "bert"
    if mode == MODEL_FUSION:
        return "finbert"
    raise ValueError(f"mode {mode} 无情感变体")


def model_paths(symbol: str, mode: str = MODEL_TS_ONLY):
    """返回 (model.h5, scaler.pkl) 路径。"""
    symbol = symbol.strip()
    if mode == MODEL_FUSION:
        return (
            MODELS_DIR / f"{symbol}_fusion_lstm.h5",
            MODELS_DIR / f"{symbol}_fusion_scaler.pkl",
        )
    if mode == MODEL_FUSION_BERT:
        return (
            MODELS_DIR / f"{symbol}_fusion_bert_lstm.h5",
            MODELS_DIR / f"{symbol}_fusion_bert_scaler.pkl",
        )
    # 新命名
    ts_model = MODELS_DIR / f"{symbol}_ts_lstm.h5"
    ts_scaler = MODELS_DIR / f"{symbol}_ts_scaler.pkl"
    if ts_model.exists():
        return ts_model, ts_scaler
    # 兼容旧版 train_lstm 命名
    return (
        MODELS_DIR / f"{symbol}_lstm_model.h5",
        MODELS_DIR / f"{symbol}_scaler.pkl",
    )
