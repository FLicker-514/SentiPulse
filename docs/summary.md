# SentiPulse 项目总结

## 目标

基于原始 BERT（`bert-base-chinese`）微调，实现中文金融新闻三分类情绪判断（负面/中性/正面）。

## 数据集

**FinanceMTEB/FinFE**（Hugging Face）

| 划分 | 样本数 |
|------|--------|
| 训练集 | 15,157 |
| 测试集 | 1,000 |

- 字段：`sentence`（中文金融文本）、`label_text`（情绪标签）、`label`（数字标签 0/1/2）
- 数据以本地 parquet 文件加载（`data/` 目录），不依赖网络

## 模型与训练

- **基座模型**：`bert-base-chinese`（通过 ModelScope 下载到 `models/bert-base-chinese/`）
- **任务**：三分类（负面/中性/正面）
- **训练参数**：learning rate 2e-5，batch size 16，3 epochs，max length 256

## 训练结果

| 指标 | 验证集 | 测试集 |
|------|--------|--------|
| Accuracy | 78.6% | **80.3%** |
| Macro F1 | 76.8% | **78.4%** |
| Weighted F1 | 78.4% | **80.1%** |

## 技术栈

- **环境管理**：uv（`pyproject.toml` + `uv.lock`）
- **框架**：PyTorch + Hugging Face Transformers + Datasets
- **启动方式**：`bash scripts/train.sh` 或 `scripts\train.bat`

## 项目结构

```
SentiPulse/
├── pyproject.toml          # uv 项目配置
├── requirements.txt        # pip 备选
├── scripts/
│   ├── train.sh            # Linux/Mac 启动脚本
│   └── train.bat           # Windows 启动脚本
├── src/
│   └── train_bert_financial_sentiment.py  # 训练主程序
├── data/                   # 本地 parquet 数据集
├── models/bert-base-chinese/  # 本地模型文件
├── docs/                   # 文档
└── outputs/bert-financial-sentiment/  # 训练产物
    ├── best_model/         # 最佳模型
    ├── eval_metrics.json   # 验证集指标
    ├── test_metrics.json   # 测试集指标
    └── labels.json         # 标签映射
```
