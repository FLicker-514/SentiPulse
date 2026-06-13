"""回测：用历史真实价格评估 ts-only vs fusion 哪个更准。"""

from __future__ import annotations

from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from theory.price_forecast.data_loader import load_merged_symbol, split_train_test
from theory.shared.config import Settings
from theory.price_forecast.lstm_predictor import forecast_from_dataframe
from theory.price_forecast.tf_backend import get_tensorflow
from theory.shared.paths import (
    ALL_TRAIN_MODES,
    FORECAST_HORIZON,
    MODEL_FUSION,
    MODEL_FUSION_BERT,
    MODEL_TS_ONLY,
    SEQ_LENGTH,
    model_paths,
)


def _pct(a: float, b: float) -> float:
    return ((a - b) / b * 100) if b else 0.0


def _direction_correct(pred_avg: float, actual_avg: float, base: float) -> bool:
    return (pred_avg >= base) == (actual_avg >= base)


def _load_mode_bundle(symbol: str, mode: str):
    tf = get_tensorflow()
    mp, sp = model_paths(symbol, mode)
    return {
        "model": tf.keras.models.load_model(mp),
        "scaler": joblib.load(sp),
        "df": load_merged_symbol(symbol, mode),
    }


def backtest_symbol(
    symbol: str,
    modes: Optional[List[str]] = None,
    n_points: int = 40,
    horizon: int = FORECAST_HORIZON,
    test_start: Optional[str] = None,
) -> dict:
    """
    在测试集（默认 2024-01-01 及以后）上滚动回测：
    每个截面用截至当日的历史预测未来 horizon 日，与真实收盘价对比。
    模型应使用 train_end=2024-01-01 训练，与此处测试集一致。
    """
    symbol = symbol.strip()
    modes = modes or list(ALL_TRAIN_MODES)

    bundles = {}
    for mode in modes:
        mp, sp = model_paths(symbol, mode)
        if mp.exists() and sp.exists():
            bundles[mode] = _load_mode_bundle(symbol, mode)

    if not bundles:
        raise FileNotFoundError(f"没有可用的已训练模型用于回测: {symbol}")

    ref_df = list(bundles.values())[0]["df"].sort_values("Date").reset_index(drop=True)
    n = len(ref_df)
    t_start = pd.Timestamp(test_start or Settings.TEST_START_DATE)

    eval_indices = [
        i
        for i in range(SEQ_LENGTH, n - horizon)
        if ref_df["Date"].iloc[i] >= t_start
    ]
    if len(eval_indices) > n_points:
        eval_indices = eval_indices[-n_points:]
    if not eval_indices:
        raise ValueError(
            f"{symbol} 在 {t_start.date()} 之后没有足够交易日做回测，请检查数据或 --test-start"
        )

    stats = {m: {"avg_errs": [], "d1_errs": [], "dir_hits": [], "ret_errs": []} for m in bundles}
    details = []

    for idx in eval_indices:
        actual_slice = ref_df.iloc[idx + 1 : idx + 1 + horizon]
        if len(actual_slice) < horizon:
            continue

        actual_prices = actual_slice["Close"].astype(float).tolist()
        actual_avg = float(np.mean(actual_prices))
        row_detail = {
            "as_of_date": str(ref_df["Date"].iloc[idx].date()),
            "last_close": round(float(ref_df["Close"].iloc[idx]), 2),
            "actual_avg_7d": round(actual_avg, 2),
            "actual_day1_close": round(actual_prices[0], 2),
        }
        actual_ret = _pct(actual_avg, row_detail["last_close"])
        row_detail["actual_return_pct"] = round(actual_ret, 3)

        for mode, bundle in bundles.items():
            hist = bundle["df"].iloc[: idx + 1].copy()
            pred = forecast_from_dataframe(
                hist, mode, bundle["model"], bundle["scaler"], horizon=horizon
            )
            pred_avg = pred["avg_lstm_price"]
            base = row_detail["last_close"]
            pred_ret = _pct(pred_avg, base)

            stats[mode]["avg_errs"].append(abs(pred_avg - actual_avg))
            stats[mode]["d1_errs"].append(
                abs(pred["forecast_7d"][0]["predicted_close"] - actual_prices[0])
            )
            stats[mode]["dir_hits"].append(_direction_correct(pred_avg, actual_avg, base))
            stats[mode]["ret_errs"].append(abs(pred_ret - actual_ret))

            row_detail[f"pred_{mode}_avg_7d"] = pred_avg
            row_detail[f"pred_{mode}_error_7d"] = round(pred_avg - actual_avg, 2)
            row_detail[f"pred_{mode}_return_pct"] = round(pred_ret, 3)

        details.append(row_detail)

    per_mode = {}
    for mode, s in stats.items():
        if not s["avg_errs"]:
            continue
        per_mode[mode] = {
            "n_eval_points": len(s["avg_errs"]),
            "mae_avg_7d_price": round(float(np.mean(s["avg_errs"])), 4),
            "mae_day1_price": round(float(np.mean(s["d1_errs"])), 4),
            "mae_return_pct": round(float(np.mean(s["ret_errs"])), 4),
            "direction_accuracy": round(float(np.mean(s["dir_hits"])), 4),
            "rmse_avg_7d_price": round(float(np.sqrt(np.mean(np.array(s["avg_errs"]) ** 2))), 4),
        }

    ranking = _rank_models(per_mode)
    report = {
        "symbol": symbol,
        "horizon_trading_days": horizon,
        "n_eval_points": per_mode[next(iter(per_mode))]["n_eval_points"],
        "eval_period": {
            "from": details[0]["as_of_date"] if details else None,
            "to": details[-1]["as_of_date"] if details else None,
        },
        "test_start": str(t_start.date()),
        "eval_note": f"测试集（>={t_start.date()}）滚动回测，与真实未来7日收盘价对比；训练集应 <{Settings.TRAIN_END_DATE}",
        "metrics_by_model": per_mode,
        "ranking": ranking,
        "sample_details": details[-5:],
    }
    report["summary_lines"] = _build_summary_lines(report)
    return report


def _rank_models(per_mode: dict) -> dict:
    scored = [
        (m, per_mode[m]["mae_avg_7d_price"], per_mode[m]["direction_accuracy"])
        for m in per_mode
    ]
    scored.sort(key=lambda x: (x[1], -x[2]))
    winner = scored[0][0]
    lines = []
    for m, mae, da in scored:
        lines.append(
            f"{m}: 7日均价MAE={mae:.2f}元, 第1日MAE={per_mode[m]['mae_day1_price']:.2f}元, "
            f"方向准确率={da*100:.1f}%"
        )
    return {
        "by_mae_avg_7d": [s[0] for s in scored],
        "winner": winner,
        "detail": lines,
    }


def _build_summary_lines(report: dict) -> List[str]:
    lines = [
        f"回测 {report['symbol']}：{report['n_eval_points']} 个截面 "
        f"({report['eval_period']['from']} ~ {report['eval_period']['to']})",
        report["eval_note"],
    ]
    lines.extend(report["ranking"]["detail"])
    w = report["ranking"]["winner"]
    lines.append(f"★ 更接近实际价格：{w}（以 7 日均价 MAE 为主）")
    ranked = report["ranking"]["by_mae_avg_7d"]
    if len(ranked) >= 2:
        win, lose = ranked[0], ranked[1]
        ma, mb = (
            report["metrics_by_model"][win]["mae_avg_7d_price"],
            report["metrics_by_model"][lose]["mae_avg_7d_price"],
        )
        if mb > 0:
            lines.append(f"  {win} 比 {lose} 的 7日均价MAE 低 {mb - ma:.2f} 元（约 {(mb-ma)/mb*100:.1f}%）")
    return lines


def format_backtest_text(report: dict) -> str:
    lines = ["", "=" * 60, f"回测对比（相对真实价格）· {report['symbol']}", "=" * 60]
    lines.extend(report.get("summary_lines", []))
    lines.append("")
    lines.append(
        f"{'模型':<10} {'MAE(7日均价)':>12} {'MAE(第1日)':>10} "
        f"{'方向准确率':>10} {'MAE(涨跌幅%)':>12}"
    )
    lines.append("-" * 58)
    for mode, m in report["metrics_by_model"].items():
        lines.append(
            f"{mode:<10} {m['mae_avg_7d_price']:>12.2f} {m['mae_day1_price']:>10.2f} "
            f"{m['direction_accuracy']*100:>9.1f}% {m['mae_return_pct']:>12.3f}"
        )
    lines.append("=" * 60)
    return "\n".join(lines)


def run_evaluate(
    symbol: str,
    mode: str = "all",
    n_points: int = 40,
    test_start: Optional[str] = None,
) -> dict:
    if mode in ("all", "both"):
        modes = list(ALL_TRAIN_MODES)
    else:
        modes = [mode]
    report = backtest_symbol(symbol, modes=modes, n_points=n_points, test_start=test_start)
    if mode in ("all", "both") and len(report["metrics_by_model"]) >= 2:
        report["head_to_head"] = {
            "winner": report["ranking"]["winner"],
            "loser": report["ranking"]["by_mae_avg_7d"][-1],
            "metrics": report["metrics_by_model"],
        }
    return report
