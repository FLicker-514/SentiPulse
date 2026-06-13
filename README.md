# SentiPulse · 舆情脉动

A 股新闻情绪 + LSTM 股价预测端到端项目（数据采集、清洗、建模、评估一体）。

## 目录结构

```
SentiPulse/
├── data_crawler/          # 自主爬取：Baostock + 东方财富 + 巨潮 + 证券时报
├── data_clean/            # 清洗 + DeepSeek 新闻摘要
├── data/
│   ├── stock/ news/      # 原始爬取数据
│   └── processed/        # 建模用数据（CSMD50_merged、情感特征、训练集）
├── theory/                # 建模：情感推理、LSTM 训练、回测、年度滚动实验
├── scripts/               # 数据导入、情感特征、实验脚本
├── src/                   # BERT 金融情感微调（课程展示用）
├── run.py                 # 统一 CLI
├── application/           # Flask API（可选）
└── docs/                  # 项目流程与原理说明
```

## 快速开始

```bash
conda activate FinBERT
cd SentiPulse

# 1. 数据已入库时，直接生成情感特征
export BERT_MODEL_PATH=../models/Bert
export SENTIMENT_MODEL_PATH=../models/FinBERT2-large
python scripts/build_sentiment_both.py --variant both --dataset CSMD50_merged

# 2. 三组 LSTM 训练
python -m theory.price_forecast.train --mode all --symbols 贵州茅台 --epochs 20 --dataset CSMD50_merged

# 3. 回测
python run.py evaluate --symbol 贵州茅台 --mode all --n-points 40

# 4. 训练数据量实验（FinBERT fusion，全股票）
python run.py year-roll-experiment --epochs 20
```

## 从清洗数据重新入库

```bash
python scripts/import_sentipulse_data.py
python run.py setup-data --dataset CSMD50_merged --rebuild
```

## 依赖

```bash
pip install -r requirements.txt
```

预训练模型放在与仓库同级的 `../models/`（`Bert/`、`FinBERT2-large/`）。

详细流程见 [docs/项目流程与原理说明.md](docs/项目流程与原理说明.md)。
