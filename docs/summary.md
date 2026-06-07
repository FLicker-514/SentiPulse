# SentiPulse 项目总结

## 目标

基于原始 BERT（`bert-base-chinese`）微调，实现中文金融新闻三分类情绪判断（负面/中性/正面）。

## 数据集

**FinanceMTEB/FinFE**（Hugging Face）

| 划分 | 样本数 |
|------|--------|
| 训练集 | 13,641 |
| 验证集 | 1,516 |
| 测试集 | 1,000 |

- 字段：`sentence`（中文金融文本）、`label_text`（情绪标签）、`label`（数字标签 0/1/2）
- 数据以本地 parquet 文件加载（`data/` 目录），不依赖网络
- 从训练集按 9:1 分层划分出验证集（stratify by label）

## 超参数

| 参数 | 值 |
|------|-----|
| 基座模型 | bert-base-chinese |
| 学习率 | 2e-5 |
| 训练 batch size | 16 |
| 评估 batch size | 32 |
| 训练轮数 | 3 |
| 最大序列长度 | 256 |
| 权重衰减 | 0.01 |
| 学习率调度器 | linear |
| 优化器 | AdamW |
| 随机种子 | 42 |
| 总训练步数 | 2,559 |

## 训练过程

| Epoch | 训练 Loss | 验证 Loss | 验证 Accuracy | 验证 Macro F1 |
|-------|----------|----------|--------------|--------------|
| 1 | 0.594 | 0.611 | 75.7% | 73.1% |
| 2 | 0.431 | 0.607 | 77.3% | 75.5% |
| 3 | 0.310 | 0.664 | 78.6% | 76.8% |

训练 loss 从 1.001 持续下降至 0.310，模型在 3 轮内稳定收敛。

## 实验结果

### 微调后 BERT

| 指标 | 验证集 | 测试集 |
|------|--------|--------|
| Accuracy | 78.6% | **80.3%** |
| Macro F1 | 76.8% | **78.4%** |
| Weighted F1 | 78.4% | **80.1%** |

### 未微调 BERT（零样本基线）

| 指标 | 验证集 | 测试集 |
|------|--------|--------|
| Accuracy | 24.3% | 23.0% |
| Macro F1 | 19.3% | 18.7% |
| Weighted F1 | 16.2% | 15.3% |

### 对比总结

| 指标 | 未微调 | 微调后 | 提升 |
|------|--------|--------|------|
| Accuracy | 23.0% | 80.3% | +57.3pp |
| Macro F1 | 18.7% | 78.4% | +59.7pp |
| Weighted F1 | 15.3% | 80.1% | +64.8pp |

未微调时分类头随机初始化，准确率低于随机猜测基线（33.3%），微调后各项指标均大幅提升，证明了领域微调的有效性。

## 技术栈

- **环境管理**：uv（`pyproject.toml` + `uv.lock`）
- **框架**：PyTorch + Hugging Face Transformers + Datasets
- **启动方式**：`bash scripts/train.sh` 或 `scripts\train.bat`

## 项目结构

```
SentiPulse/
├── pyproject.toml                          # uv 项目配置
├── requirements.txt                        # pip 备选
├── scripts/
│   ├── train.sh                            # Linux/Mac 启动脚本
│   └── train.bat                           # Windows 启动脚本
├── src/
│   ├── train_bert_financial_sentiment.py   # 微调训练主程序
│   └── eval_untuned_baseline.py            # 零样本基线评估
├── data/                                   # 本地 parquet 数据集
├── models/bert-base-chinese/               # 本地模型文件（不纳入 git）
├── docs/
│   └── summary.md                          # 本文档
└── outputs/
    ├── bert-financial-sentiment/           # 微调产物
    │   ├── best_model/                     # 最佳模型
    │   ├── checkpoint-*/                   # 训练检查点
    │   ├── hyperparameters.json            # 超参数记录
    │   ├── training_loss.json              # 训练/验证 loss 曲线
    │   ├── eval_metrics.json               # 验证集指标
    │   ├── test_metrics.json               # 测试集指标
    │   └── labels.json                     # 标签映射
    └── bert-untuned-baseline/              # 零样本基线结果
        ├── val_metrics.json
        └── test_metrics.json
```
