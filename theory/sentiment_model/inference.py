""" (3) 情感分析：使用本地 FinBERT-zh（data/models/FinBERT-zh）对新闻做二分类推理。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Union

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from theory.shared.paths import resolve_sentiment_model_dir

MAX_TEXT_LEN = 512

_POSITIVE_KEYS = frozenset(
    {"positive", "pos", "bull", "bullish", "积极", "正面", "利好", "label_1"}
)
_NEGATIVE_KEYS = frozenset(
    {"negative", "neg", "bear", "bearish", "消极", "负面", "利空", "label_0"}
)


def _normalize_label(raw: str) -> str:
    key = raw.lower().strip()
    if key in _POSITIVE_KEYS or "pos" in key or "bull" in key or "积极" in raw or "正面" in raw:
        return "positive"
    if key in _NEGATIVE_KEYS or "neg" in key or "bear" in key or "消极" in raw or "负面" in raw:
        return "negative"
    if "neutral" in key or "中性" in raw:
        return "neutral"
    return key


@lru_cache(maxsize=4)
def _load_model(model_dir_str: str):
    model_dir = Path(model_dir_str)
    if not model_dir.is_dir():
        raise FileNotFoundError(
            f"未找到情感模型目录: {model_dir}\n"
            "请设置 SENTIMENT_MODEL_PATH / BERT_MODEL_PATH，或将权重放到 data/models/ 或 ../models/"
        )
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_dir), local_files_only=True
    )
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    id2label = getattr(model.config, "id2label", None) or {}
    if not id2label:
        n = int(getattr(model.config, "num_labels", 2))
        id2label = {i: f"LABEL_{i}" for i in range(n)}

    return tokenizer, model, device, id2label


def _empty_sentiment() -> Dict[str, float]:
    return {
        "label": "neutral",
        "confidence": 0.0,
        "positive": 0.0,
        "negative": 0.0,
        "neutral": 1.0,
        "signed_score": 0.0,
    }


def sentiment_probabilities(
    text: str,
    *,
    model_dir: Optional[Path] = None,
    variant: str = "finbert",
) -> Dict[str, float]:
    """
    对新闻文本推理，返回正向/负向概率及融合用有符号分数。

    variant: finbert（微调 FinBERT-zh）| bert（未微调 Bert）
    signed_score = P(positive) - P(negative)，范围约 [-1, 1]。
    """
    if not text or not text.strip():
        return _empty_sentiment()

    resolved = model_dir or resolve_sentiment_model_dir(variant)
    tokenizer, model, device, id2label = _load_model(str(resolved.resolve()))
    encoded = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_TEXT_LEN,
        padding=False,
    )
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1)[0].cpu().tolist()

    bucket: Dict[str, float] = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
    for idx, prob in enumerate(probs):
        raw = id2label.get(idx, id2label.get(str(idx), f"LABEL_{idx}"))
        norm = _normalize_label(str(raw))
        if norm in bucket:
            bucket[norm] += float(prob)
        else:
            bucket.setdefault(norm, 0.0)
            bucket[norm] += float(prob)

    pos = bucket["positive"]
    neg = bucket["negative"]
    neu = bucket.get("neutral", 0.0)
    signed = pos - neg

    if pos >= neg and pos >= neu:
        label, confidence = "positive", pos
    elif neg >= pos and neg >= neu:
        label, confidence = "negative", neg
    else:
        label, confidence = "neutral", neu

    return {
        "label": label,
        "confidence": round(confidence, 6),
        "positive": round(pos, 6),
        "negative": round(neg, 6),
        "neutral": round(neu, 6),
        "signed_score": round(signed, 6),
    }


def analyze_sentiment(text: str) -> List[dict]:
    """兼容旧 API：返回各标签及概率列表。"""
    p = sentiment_probabilities(text)
    out = [
        {"label": "positive", "score": p["positive"]},
        {"label": "negative", "score": p["negative"]},
    ]
    if p["neutral"] > 0:
        out.append({"label": "neutral", "score": p["neutral"]})
    return out


def parse_sentiment_result(
    results: Union[List[dict], Dict[str, float], str],
) -> Tuple[str, float, float]:
    """
    解析情感结果。

    返回 (label, confidence, signed_score)。
    """
    if isinstance(results, str):
        p = sentiment_probabilities(results)
        return p["label"], p["confidence"], p["signed_score"]
    if isinstance(results, dict) and "signed_score" in results:
        return results["label"], results["confidence"], results["signed_score"]
    if not results:
        p = _empty_sentiment()
        return p["label"], p["confidence"], p["signed_score"]
    item = results[0]
    label = _normalize_label(str(item.get("label", "neutral")))
    score = float(item.get("score", 0.0))
    signed = score if label == "positive" else (-score if label == "negative" else 0.0)
    return label, score, signed
