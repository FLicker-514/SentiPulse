import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # FinBERT 等最小环境可不装 python-dotenv，直接用系统环境变量


class Settings:
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    SENTIMENT_IMPACT_BETA = float(os.getenv("SENTIMENT_IMPACT_BETA", "0.02"))
    SENTIMENT_MODEL_PATH = os.getenv("SENTIMENT_MODEL_PATH", "")  # FinBERT2-large 预训练权重
    BERT_MODEL_PATH = os.getenv("BERT_MODEL_PATH", "")  # 未微调 bert-base-chinese
    TRAIN_END_DATE = os.getenv("TRAIN_END_DATE", "2024-01-01")
    TEST_START_DATE = os.getenv("TEST_START_DATE", "2024-01-01")
