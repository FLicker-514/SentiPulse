# （3）情感分析

支持两套情感模型对比：

| variant | 默认路径 | 用途 |
|---------|----------|------|
| `finbert` | `data/models/FinBERT-zh/` 或 `../models/FinBERT-zh` | 微调后 FinBERT，用于 `fusion` |
| `bert` | `data/models/Bert/` 或 `../models/Bert` | 未微调 Bert，用于 `fusion-bert` |

## 模型目录

默认加载中文模型：

```
data/models/FinBERT-zh/
├── config.json
├── model.safetensors
├── tokenizer_config.json
├── vocab.txt
└── ...
```

可通过环境变量覆盖路径：

```bash
export SENTIMENT_MODEL_PATH=../models/FinBERT-zh   # 微调 FinBERT
export BERT_MODEL_PATH=../models/Bert              # 未微调 Bert
```

对比两模型在同一批新闻上的判断差异：

```bash
python run.py compare-sentiment -n 50 --seed 42 --dataset CSMD50_merged
```

### 依赖版本

需 `transformers>=4.46` 与 `huggingface-hub>=1.0` 配套。若 import 报错，执行：

```bash
pip install -U "transformers>=4.46" "huggingface-hub>=0.23" safetensors
```

## 输出字段

| 字段 | 含义 |
|------|------|
| `positive` | 正向类概率 |
| `negative` | 负向类概率 |
| `signed_score` | `positive - negative`，用于 `fusion` 修正 LSTM 价格 |
| `label` / `confidence` | 主类别及置信度 |

融合公式：`adjusted_price = lstm_price × (1 + β × signed_score)`

## 用法

```python
from theory.sentiment_model.inference import sentiment_probabilities

sentiment_probabilities("公司发布超预期财报...")
```

### 随机抽样批量测试

从 `data/processed/CSMD50/news/` 按条随机抽取新闻：

```bash
python run.py test-sentiment -n 10              # 全市场随机 10 条
python run.py test-sentiment -n 5 --symbol 贵州茅台 --seed 42
```

## 预训练

`pretrain.py` 仍为占位；当前直接使用你提供的 FinBERT 权重。
