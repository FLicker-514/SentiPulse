# （4）股价时序预测

## 数据划分（默认）

| 集合 | 时间范围 | 用途 |
|------|----------|------|
| **训练集** | `Date < 2024-01-01` | `train`（约 2021–2023） |
| **测试集** | `Date >= 2024-01-01` | `evaluate` 与真实价格对比 |

可通过 `--train-end` / `--test-start` 或环境变量 `TRAIN_END_DATE` 修改。

## 三种模型（对比实验）

| 模式 | 情感模型 | 输入特征 | 权重文件 |
|------|----------|----------|----------|
| `ts-only` | 无 | 仅 `Close` | `{股票}_ts_lstm.h5` |
| `fusion-bert` | 未微调 Bert | `Close` + `signed_score` | `{股票}_fusion_bert_lstm.h5` |
| `fusion` | FinBERT-zh（微调） | `Close` + `signed_score` | `{股票}_fusion_lstm.h5` |

## 训练流程（GPU 服务器）

```bash
# 1. 数据就绪
python run.py setup-data --rebuild

# 2. 生成两组日度情感（Bert + FinBERT-zh）
python run.py build-sentiment --variant both --dataset CSMD50_merged

# 3. 对比两模型情感判断差异（可选）
python run.py compare-sentiment -n 50 --seed 42

# 4. 三组一起训练
python run.py train --mode all --symbols 贵州茅台 --epochs 20 --dataset CSMD50_merged --rebuild-sentiment

# 5. 三组回测对比
python run.py evaluate --symbol 贵州茅台 --mode all
```

## 预测 vs 回测

| 命令 | 作用 |
|------|------|
| `evaluate` | **与真实历史价格对比**，在验证集上滚动回测，判断 ts-only / fusion 哪个更准 |
| `predict` | 用最新数据预测未来 7 日（样本结束后无真实值可对比） |

```bash
# 回测（写报告用这个）
python run.py evaluate --symbol 贵州茅台 --mode both --n-points 40

python run.py predict --symbol 贵州茅台 --mode both
```

回测指标（越小越好）：`MAE(7日均价)`、`MAE(第1日)`、`方向准确率`（越大越好）。

## 文件

| 文件 | 作用 |
|------|------|
| `sentiment_features.py` | 新闻 → `sentiment_daily.csv` |
| `train.py` | 统一训练入口 |
| `lstm_predictor.py` | 加载对应权重推理 |
| `pipeline.py` | 端到端（含 `both` 对比） |
| `fusion.py` | 可选：训练后推理期再叠加一层情绪修正 |
