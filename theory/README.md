# 理论部分（Theory）

| 目录 | 模块 |
|------|------|
| `data_crawler/` | （1）数据爬取 — `news_scraper.py`、`price_data_collection.py` |
| `data_cleaning/` | （2）清洗 + 蒸馏 — `setup_csmd.py`、`llm_distill.py` |
| `sentiment_model/` | （3）情感 — `inference.py`、`pretrain.py`（占位） |
| `price_forecast/` | （4）LSTM + 情绪融合 |
| `shared/` | `paths.py`、`config.py` |

**数据均在项目根目录 `data/`**，见 [data/README.md](../data/README.md)。
