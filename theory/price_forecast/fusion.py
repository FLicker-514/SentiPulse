""" (4) 情绪修正 LSTM 预测价格。"""

from typing import Optional

from theory.shared.config import Settings


def label_to_direction(label: str) -> int:
    label = label.lower()
    if any(k in label for k in ("bull", "pos", "积极", "正面", "利好")):
        return 1
    if any(k in label for k in ("bear", "neg", "消极", "负面", "利空")):
        return -1
    return 0


def sentiment_signal(
    label: str,
    confidence: float,
    signed_score: Optional[float] = None,
) -> float:
    """融合用情绪信号，优先使用 FinBERT 的 signed_score（正向概率 − 负向概率）。"""
    if signed_score is not None:
        return max(-1.0, min(1.0, float(signed_score)))
    return label_to_direction(label) * min(max(confidence, 0.0), 1.0)


def fuse_predictions(
    lstm_price: float,
    last_close: float,
    sentiment_label: str,
    sentiment_confidence: float,
    lstm_confidence: float = 0.5,
    beta: Optional[float] = None,
    sentiment_signed_score: Optional[float] = None,
    sentiment_positive: Optional[float] = None,
    sentiment_negative: Optional[float] = None,
) -> dict:
    beta = beta if beta is not None else Settings.SENTIMENT_IMPACT_BETA
    sig = sentiment_signal(
        sentiment_label,
        sentiment_confidence,
        signed_score=sentiment_signed_score,
    )
    adjusted_price = lstm_price * (1.0 + beta * sig)
    lstm_return = (lstm_price - last_close) / last_close if last_close else 0.0
    adjusted_return = (adjusted_price - last_close) / last_close if last_close else 0.0
    if sentiment_confidence >= 0.7:
        sentiment_weight = min(0.5, sentiment_confidence * 0.5)
    else:
        sentiment_weight = max(0.0, sentiment_confidence * 0.25)
    lstm_weight = max(0.5, 1.0 - sentiment_weight)
    return {
        "last_close": round(last_close, 2),
        "lstm_price": round(lstm_price, 2),
        "adjusted_price": round(adjusted_price, 2),
        "sentiment_signal": round(sig, 4),
        "sentiment_impact_pct": round(beta * sig * 100, 3),
        "lstm_return_pct": round(lstm_return * 100, 3),
        "adjusted_return_pct": round(adjusted_return * 100, 3),
        "direction_lstm": "UP" if lstm_price >= last_close else "DOWN",
        "direction_final": "UP" if adjusted_price >= last_close else "DOWN",
        "weight_distribution": {
            "sentiment_pct": round(sentiment_weight * 100, 2),
            "lstm_pct": round(lstm_weight * 100, 2),
        },
        "lstm_confidence": round(lstm_confidence, 4),
        "sentiment_label": sentiment_label,
        "sentiment_confidence": round(sentiment_confidence, 4),
        "sentiment_positive": round(sentiment_positive, 4)
        if sentiment_positive is not None
        else None,
        "sentiment_negative": round(sentiment_negative, 4)
        if sentiment_negative is not None
        else None,
        "sentiment_signed_score": round(sentiment_signed_score, 4)
        if sentiment_signed_score is not None
        else None,
    }
