"""
(3) 情感分析模型预训练（待实现）。

计划：
  - 使用 CSMD 新闻 text + 情绪标签（或 LLM 蒸馏标签）微调 FinBERT / 中文 RoBERTa
  - 训练数据来自 data/processed/CSMD50/news/
  - 可参考 LightQuant 的 PEN、FinGPT-Sentiment v3 LoRA 流程
"""


def pretrain(
    data_dir: str = "data/processed/CSMD50/news",
    output_dir: str = "models/sentiment_pretrained",
    epochs: int = 3,
):
    raise NotImplementedError(
        "预训练流程尚未实现。当前请使用 data/models/FinBERT-zh 本地权重做推理。"
    )


if __name__ == "__main__":
    print(__doc__)
