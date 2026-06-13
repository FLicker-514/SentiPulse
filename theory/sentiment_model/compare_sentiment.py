"""对比未微调 Bert 与 FinBERT-zh 在同一批新闻上的情感判断差异。"""

from __future__ import annotations

import random
from typing import List, Optional

from theory.sentiment_model.inference import sentiment_probabilities
from theory.sentiment_model.sample_news import iter_news_items


def compare_sentiment_models(
    n: int = 50,
    symbol: Optional[str] = None,
    seed: Optional[int] = None,
    news_root=None,
) -> dict:
    pool = list(iter_news_items(symbol=symbol, news_root=news_root))
    if not pool:
        raise FileNotFoundError("未找到新闻样本，请先运行 setup-data")

    if seed is not None:
        random.seed(seed)
    k = min(n, len(pool))
    samples = random.sample(pool, k)

    rows = []
    label_agree = 0
    signed_diffs = []

    for item in samples:
        bert = sentiment_probabilities(item.text, variant="bert")
        finbert = sentiment_probabilities(item.text, variant="finbert")
        agree = bert["label"] == finbert["label"]
        if agree:
            label_agree += 1
        diff = finbert["signed_score"] - bert["signed_score"]
        signed_diffs.append(diff)
        rows.append(
            {
                "symbol": item.symbol,
                "date": item.date,
                "text_preview": item.text[:80] + ("..." if len(item.text) > 80 else ""),
                "bert_label": bert["label"],
                "finbert_label": finbert["label"],
                "bert_signed_score": bert["signed_score"],
                "finbert_signed_score": finbert["signed_score"],
                "signed_score_diff": round(diff, 6),
                "label_agree": agree,
            }
        )

    return {
        "sampled": k,
        "seed": seed,
        "symbol_filter": symbol,
        "label_agreement_rate": round(label_agree / k, 4),
        "mean_signed_score_diff": round(sum(signed_diffs) / k, 6),
        "mean_abs_signed_score_diff": round(sum(abs(d) for d in signed_diffs) / k, 6),
        "note": "label_agreement_rate 越高表示两模型情感分类越一致；signed_score_diff=FinBERT-Bert",
        "results": rows,
    }
