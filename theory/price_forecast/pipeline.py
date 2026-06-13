""" (4) 端到端预测：ts-only / fusion / both。"""

from typing import List, Optional

from theory.sentiment_model.inference import sentiment_probabilities
from theory.price_forecast.fusion import fuse_predictions
from theory.price_forecast.lstm_predictor import forecast_stock, load_price_data
from theory.price_forecast.news_loader import resolve_news_text
from theory.shared.paths import (
    ALL_TRAIN_MODES,
    MODEL_FUSION,
    MODEL_FUSION_BERT,
    MODEL_TS_ONLY,
    is_fusion_mode,
    model_paths,
)


def list_available_symbols() -> List[str]:
    return sorted(load_price_data()["Symbol"].unique().tolist())


def _pct_change(pred: float, base: float) -> float:
    return ((pred - base) / base * 100) if base else 0.0


def _direction(pred: float, base: float) -> str:
    return "UP" if pred >= base else "DOWN"


def build_comparison(
    symbol: str,
    predictions: dict,
    sentiment: Optional[dict] = None,
    fusion_posthoc: Optional[dict] = None,
) -> dict:
    """生成 ts-only vs fusion 综合对比表。"""
    last_close = None
    last_date = None
    rows = {}

    for mode, pred in predictions.items():
        lc = pred["last_close"]
        last_close = last_close or lc
        last_date = last_date or pred.get("last_date")
        avg = pred["avg_lstm_price"]
        rows[mode] = {
            "avg_predicted_close_7d": avg,
            "return_pct_vs_last_close": round(_pct_change(avg, lc), 3),
            "direction": _direction(avg, lc),
            "avg_confidence": pred["avg_lstm_confidence"],
            "day1_predicted_close": pred["forecast_7d"][0]["predicted_close"],
            "day1_return_pct": pred["forecast_7d"][0]["percent_change"],
        }

    comp = {
        "symbol": symbol,
        "last_close": last_close,
        "last_date": last_date,
        "models": rows,
    }

    if sentiment:
        comp["news_sentiment"] = {
            "label": sentiment["label"],
            "signed_score": sentiment["signed_score"],
            "positive": sentiment["positive"],
            "negative": sentiment["negative"],
        }

    if MODEL_TS_ONLY in rows and MODEL_FUSION in rows:
        ts_avg = rows[MODEL_TS_ONLY]["avg_predicted_close_7d"]
        fu_avg = rows[MODEL_FUSION]["avg_predicted_close_7d"]
        diff = fu_avg - ts_avg
        comp["diff_fusion_minus_ts_only"] = {
            "price": round(diff, 2),
            "price_pct_of_ts": round(_pct_change(fu_avg, ts_avg), 3),
            "interpretation": (
                "FinBERT融合 7 日均价高于纯时序"
                if diff > 0
                else "FinBERT融合 7 日均价低于纯时序" if diff < 0
                else "两模型 7 日均价一致"
            ),
        }
        comp["direction_agreement"] = (
            rows[MODEL_TS_ONLY]["direction"] == rows[MODEL_FUSION]["direction"]
        )

    if MODEL_TS_ONLY in rows and MODEL_FUSION_BERT in rows:
        ts_avg = rows[MODEL_TS_ONLY]["avg_predicted_close_7d"]
        bert_avg = rows[MODEL_FUSION_BERT]["avg_predicted_close_7d"]
        diff = bert_avg - ts_avg
        comp["diff_fusion_bert_minus_ts_only"] = {
            "price": round(diff, 2),
            "price_pct_of_ts": round(_pct_change(bert_avg, ts_avg), 3),
        }

    if MODEL_FUSION_BERT in rows and MODEL_FUSION in rows:
        bert_avg = rows[MODEL_FUSION_BERT]["avg_predicted_close_7d"]
        fin_avg = rows[MODEL_FUSION]["avg_predicted_close_7d"]
        comp["diff_fusion_finbert_minus_fusion_bert"] = {
            "price": round(fin_avg - bert_avg, 2),
            "price_pct_of_bert": round(_pct_change(fin_avg, bert_avg), 3),
        }

    if fusion_posthoc and MODEL_TS_ONLY in rows:
        ts_avg = rows[MODEL_TS_ONLY]["avg_predicted_close_7d"]
        post_avg = fusion_posthoc["adjusted_price"]
        comp["posthoc_on_ts_only"] = {
            "description": "在 ts-only 预测价上再按 FinBERT 情绪做系数修正（非 fusion 训练权重）",
            "adjusted_price_7d_avg": post_avg,
            "return_pct_vs_last_close": fusion_posthoc["adjusted_return_pct"],
            "sentiment_impact_pct": fusion_posthoc["sentiment_impact_pct"],
            "diff_vs_ts_only_price": round(post_avg - ts_avg, 2),
            "diff_vs_fusion_lstm_price": round(
                post_avg - rows.get(MODEL_FUSION, {}).get("avg_predicted_close_7d", post_avg),
                2,
            )
            if MODEL_FUSION in rows
            else None,
        }

    # 简要结论（便于写报告）
    lines = [f"基准收盘价 {last_close}（{last_date}）"]
    if MODEL_TS_ONLY in rows:
        r = rows[MODEL_TS_ONLY]
        lines.append(
            f"纯时序 LSTM：7日均价 {r['avg_predicted_close_7d']}（{r['return_pct_vs_last_close']:+.3f}%），方向 {r['direction']}"
        )
    if MODEL_FUSION_BERT in rows:
        r = rows[MODEL_FUSION_BERT]
        lines.append(
            f"Bert融合 LSTM：7日均价 {r['avg_predicted_close_7d']}（{r['return_pct_vs_last_close']:+.3f}%），方向 {r['direction']}"
        )
    if MODEL_FUSION in rows:
        r = rows[MODEL_FUSION]
        lines.append(
            f"FinBERT融合 LSTM：7日均价 {r['avg_predicted_close_7d']}（{r['return_pct_vs_last_close']:+.3f}%），方向 {r['direction']}"
        )
    if sentiment:
        lines.append(
            f"新闻情感：{sentiment['label']}，signed_score={sentiment['signed_score']:.4f}"
        )
    if "diff_fusion_minus_ts_only" in comp:
        d = comp["diff_fusion_minus_ts_only"]
        lines.append(f"融合相对时序：价差 {d['price']:+.2f} 元（{d['price_pct_of_ts']:+.3f}%）")
    comp["summary_lines"] = lines

    return comp


def format_comparison_text(comparison: dict) -> str:
    """终端可读的综合对比。"""
    lines = ["", "=" * 60, f"综合对比 · {comparison['symbol']}", "=" * 60]
    lines.extend(comparison.get("summary_lines", []))
    if "models" in comparison:
        lines.append("")
        lines.append(f"{'模型':<12} {'7日均价':>10} {'相对昨收':>10} {'方向':>6} {'置信度':>8}")
        lines.append("-" * 52)
        for mode, r in comparison["models"].items():
            lines.append(
                f"{mode:<12} {r['avg_predicted_close_7d']:>10.2f} "
                f"{r['return_pct_vs_last_close']:>+9.3f}% {r['direction']:>6} "
                f"{r['avg_confidence']:>8.4f}"
            )
    if comparison.get("posthoc_on_ts_only"):
        p = comparison["posthoc_on_ts_only"]
        lines.append("")
        lines.append(
            f"事后情绪修正(ts-only×β×情感): 均价≈{p['adjusted_price_7d_avg']:.2f}，"
            f"情绪影响 {p['sentiment_impact_pct']:+.3f}%"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def run_prediction(
    symbol: str,
    mode: str = MODEL_FUSION,
    news_text: Optional[str] = None,
    use_news_api: bool = True,
) -> dict:
    """
    mode:
      - ts-only: 仅 LSTM（收盘价序列）
      - fusion-bert / fusion: LSTM（收盘价 + 日度情感）
      - all / both: 同时返回三种/两种模型结果便于对比
    """
    symbol = symbol.strip()
    if mode in ("all", "both"):
        modes = list(ALL_TRAIN_MODES)
    else:
        modes = [mode]

    news_body, news_source = "", "none"
    sent_bert = None
    sent_finbert = None
    if any(is_fusion_mode(m) for m in modes):
        news_body, news_source = resolve_news_text(symbol, news_text, use_api=use_news_api)
        sent_finbert = sentiment_probabilities(news_body, variant="finbert")
        sent_bert = sentiment_probabilities(news_body, variant="bert")

    out = {
        "symbol": symbol,
        "requested_mode": mode,
        "news_source": news_source,
        "news_preview": news_body[:500] + ("..." if len(news_body) > 500 else ""),
    }
    if sent_finbert is not None:
        out["sentiment_finbert"] = sent_finbert
        out["sentiment_bert"] = sent_bert
        out["sentiment"] = sent_finbert

    predictions = {}
    missing = {}
    for m in modes:
        model_p, scaler_p = model_paths(symbol, m)
        if not (model_p.exists() and scaler_p.exists()):
            missing[m] = (
                f"缺少权重: {model_p.name} / {scaler_p.name}，"
                f"请先: python run.py train --mode {m} --symbols {symbol}"
            )
            continue
        live = None
        if m == MODEL_FUSION and sent_finbert:
            live = sent_finbert["signed_score"]
        elif m == MODEL_FUSION_BERT and sent_bert:
            live = sent_bert["signed_score"]
        predictions[m] = forecast_stock(symbol, mode=m, live_sentiment=live)

    if missing:
        out["missing_models"] = missing
    if not predictions:
        lines = "\n".join(f"  [{k}] {v}" for k, v in missing.items())
        raise FileNotFoundError(f"没有可用的已训练模型:\n{lines}")

    out["predictions"] = predictions

    fusion_posthoc = None
    if sent_finbert and MODEL_TS_ONLY in predictions:
        ts = predictions[MODEL_TS_ONLY]
        fusion_posthoc = fuse_predictions(
            lstm_price=ts["avg_lstm_price"],
            last_close=ts["last_close"],
            sentiment_label=sent_finbert["label"],
            sentiment_confidence=sent_finbert["confidence"],
            lstm_confidence=ts["avg_lstm_confidence"],
            sentiment_signed_score=sent_finbert["signed_score"],
            sentiment_positive=sent_finbert["positive"],
            sentiment_negative=sent_finbert["negative"],
        )
        out["fusion_posthoc"] = fusion_posthoc

    if mode in ("all", "both") and len(predictions) >= 1:
        out["comparison"] = build_comparison(
            symbol,
            predictions,
            sentiment=sent_finbert,
            fusion_posthoc=fusion_posthoc,
        )
        out["comparison"]["note"] = (
            "此为多模型预测值对比，未含真实股价。"
            "与真实价格孰优请运行: python run.py evaluate --symbol "
            + symbol
            + " --mode all"
        )

    primary = MODEL_FUSION if MODEL_FUSION in predictions else MODEL_TS_ONLY
    out["lstm"] = predictions[primary]
    if mode == MODEL_FUSION and "fusion_posthoc" in out:
        out["fusion"] = out["fusion_posthoc"]

    return out
