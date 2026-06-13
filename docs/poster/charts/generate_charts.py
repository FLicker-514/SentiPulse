"""Generate polished charts for SentiPulse poster using seaborn."""
import json, pathlib, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

HERE = pathlib.Path(__file__).resolve().parent
PROJ = HERE.parent.parent.parent  # SentiPulse root
OUT = HERE.parent / "public"  # Output to public/ for Vue serving

sns.set_theme(style="whitegrid", context="notebook", font_scale=1.15)

NAVY = "#0a1628"
GOLD = "#c8963e"
TEAL = "#0d9488"
BLUE = "#3b82f6"
RED = "#ef4444"
PURPLE = "#8b5cf6"
GRAY = "#94a3b8"
DARK_GRAY = "#334155"

plt.rcParams.update({
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "DejaVu Sans"],
    "axes.unicode_minus": False,
})


def chart_price_trends():
    df = pd.read_csv(PROJ / "data_clean" / "output" / "stock_daily_cleaned.csv",
                     parse_dates=["Date"])
    syms = [600519,601398,600276,688041,688111,603288]
    names = {600519:"贵州茅台",601398:"工商银行",600276:"恒瑞医药",
             688041:"海光信息",688111:"金山办公",603288:"海天味业"}
    colors = [GOLD, NAVY, BLUE, RED, TEAL, PURPLE]

    fig, ax = plt.subplots(figsize=(10, 5.2))
    for sym, c in zip(syms, colors):
        sub = df[df["StockCode"] == sym].sort_values("Date")
        norm = sub["Close"].values / sub["Close"].values[0] * 100
        ax.plot(sub["Date"], norm, color=c, linewidth=1.8, label=names[sym])

    ax.set_title("Representative Stock Price Trends  (normalized, 2025.01 – 2026.06)",
                 fontsize=14, fontweight="bold", color=NAVY, pad=14)
    ax.legend(fontsize=9, loc="upper left", frameon=True, edgecolor="#ddd", fancybox=True)
    ax.set_ylabel("Normalized Close (base=100)", fontsize=11, color=DARK_GRAY)
    ax.tick_params(labelsize=9, colors=DARK_GRAY)
    sns.despine()
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "price_trends.png", dpi=180)
    plt.close(fig)
    print("  -> price_trends.png")


def chart_training_loss():
    with open(PROJ / "outputs" / "bert-financial-sentiment" / "training_loss.json") as f:
        data = json.load(f)
    train = [(p["step"], p["loss"]) for p in data["train"]]
    eval_ = [(p["epoch"], p["eval_loss"], p["eval_accuracy"]) for p in data["eval"]]

    fig, ax1 = plt.subplots(figsize=(10, 4.8))
    steps, losses = zip(*train)
    ax1.fill_between(steps, losses, alpha=0.12, color=GOLD)
    ax1.plot(steps, losses, color=GOLD, linewidth=1.5, label="Training Loss")
    ax1.set_xlabel("Training Steps", fontsize=11, color=DARK_GRAY)
    ax1.set_ylabel("Training Loss", fontsize=11, color=GOLD, fontweight="bold")
    ax1.tick_params(axis='y', labelcolor=GOLD, labelsize=9)
    ax1.tick_params(axis='x', labelsize=9, colors=DARK_GRAY)

    ax2 = ax1.twinx()
    epochs, eval_losses, eval_accs = zip(*eval_)
    x_positions = np.linspace(0, max(steps), len(epochs))
    for xi, ep, acc in zip(x_positions, epochs, eval_accs):
        ax2.plot(xi, acc, "o", color=TEAL, markersize=15, markeredgecolor="white",
                 markeredgewidth=2, zorder=5)
        ax2.annotate(f"Epoch {int(ep)}\n{acc:.1%}", (xi, acc),
                     textcoords="offset points", xytext=(0, 20), fontsize=9.5,
                     color=TEAL, fontweight="bold", ha="center")
    ax2.plot(x_positions, eval_accs, color=TEAL, linewidth=1, linestyle="--", alpha=0.5)
    ax2.set_ylabel("Validation Accuracy", fontsize=11, color=TEAL, fontweight="bold")
    ax2.tick_params(axis='y', labelcolor=TEAL, labelsize=9)
    ax2.set_ylim(0.70, 0.85)
    ax1.set_title("BERT Fine-tuning — Training Loss & Validation Accuracy",
                  fontsize=14, fontweight="bold", color=NAVY, pad=14)
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "training_loss.png", dpi=180)
    plt.close(fig)
    print("  -> training_loss.png")


def chart_news_distribution():
    companies = ["交通银行","恒瑞医药","贵州茅台","海尔智家","海光信息",
                 "工商银行","海天味业","国电南瑞","金山办公","保利发展"]
    counts = [1544, 1358, 1452, 1014, 908, 883, 744, 673, 643, 636]
    months_str = ["2025\n01","02","03","04","05","06","07","08","09","10","11","12",
                  "2026\n01","02","03","04","05","06"]
    monthly = [23,8,239,331,220,249,88,297,236,197,184,913,863,525,1246,1635,1102,291]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.8),
                                   gridspec_kw={'width_ratios': [1, 1.3]})
    idx_sorted = np.argsort(counts)
    sorted_names = [companies[i] for i in idx_sorted]
    sorted_counts = [counts[i] for i in idx_sorted]
    palette = [GOLD if c == max(counts) else TEAL if c == min(counts) else NAVY for c in sorted_counts]
    bars = ax1.barh(range(len(sorted_names)), sorted_counts, color=palette, height=0.6,
                    edgecolor="white", linewidth=0.8)
    ax1.set_yticks(range(len(sorted_names)))
    ax1.set_yticklabels(sorted_names, fontsize=10)
    ax1.invert_yaxis()
    ax1.set_xlabel("Article Count", fontsize=11, color=DARK_GRAY)
    ax1.tick_params(labelsize=9, colors=DARK_GRAY)
    for bar, c in zip(bars, sorted_counts):
        ax1.text(bar.get_width() + 18, bar.get_y() + bar.get_height()/2,
                 str(c), va="center", fontsize=9.5, fontweight="bold", color=NAVY)
    ax1.set_xlim(0, 1950)
    ax1.set_title("By Company", fontsize=12, fontweight="bold", color=NAVY)

    x = range(len(months_str))
    ax2.fill_between(x, monthly, alpha=0.18, color=TEAL)
    ax2.plot(x, monthly, color=TEAL, linewidth=2, marker="o", markersize=5,
             markerfacecolor="white", markeredgecolor=TEAL, markeredgewidth=2)
    ax2.set_xticks(x[::3])
    ax2.set_xticklabels([months_str[i] for i in x[::3]], fontsize=9, rotation=0)
    ax2.set_ylabel("Monthly Count", fontsize=11, color=DARK_GRAY)
    ax2.tick_params(labelsize=9, colors=DARK_GRAY)
    peak_i = monthly.index(max(monthly))
    ax2.annotate(f"Peak: {monthly[peak_i]}  (2026-04)", (peak_i, monthly[peak_i]),
                 textcoords="offset points", xytext=(12, 12), fontsize=9.5,
                 color=NAVY, fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color=GOLD, lw=1.5))
    ax2.set_title("By Month", fontsize=12, fontweight="bold", color=NAVY)

    fig.suptitle("News Data Distribution  (Total 9,855 Articles)", fontsize=14,
                 fontweight="bold", color=NAVY, y=1.04)
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "news_distribution.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("  -> news_distribution.png")


def chart_bert_comparison():
    metrics = ["Accuracy", "Macro F1", "Weighted F1"]
    fine_tuned = [80.3, 78.4, 80.1]
    untuned = [23.0, 18.7, 15.3]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    x = np.arange(len(metrics))
    width = 0.28

    ax.bar(x - width/2, fine_tuned, width, color=GOLD, edgecolor="white",
           linewidth=1, label="Fine-tuned BERT", zorder=3)
    ax.bar(x + width/2, untuned, width, color=GRAY, edgecolor="white",
           linewidth=1, label="Untuned Baseline", zorder=3)

    for i, (ft, un) in enumerate(zip(fine_tuned, untuned)):
        ax.text(x[i] - width/2, ft + 2.5, f"{ft}%", ha="center", fontsize=12, fontweight="bold", color=GOLD)
        ax.text(x[i] + width/2, un + 2.5, f"{un}%", ha="center", fontsize=11, color=DARK_GRAY)

    improvements = ["+57.3pp", "+59.7pp", "+64.8pp"]
    for i, imp in enumerate(improvements):
        ax.annotate(imp, (x[i], max(fine_tuned[i], untuned[i]) + 13),
                    ha="center", fontsize=11, fontweight="bold", color=TEAL,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                              edgecolor=TEAL, alpha=0.85))

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=13, fontweight="bold", color=NAVY)
    ax.set_ylim(0, 118)
    ax.set_ylabel("Score (%)", fontsize=12, color=DARK_GRAY)
    ax.legend(fontsize=10.5, frameon=True, edgecolor="#ddd", fancybox=True,
              loc="lower right", bbox_to_anchor=(0.99, 0.02))
    ax.tick_params(labelsize=10, colors=DARK_GRAY)
    sns.despine()
    ax.set_title("BERT Sentiment Classification — Test Set  (FinanceMTEB/FinFE)",
                 fontsize=14, fontweight="bold", color=NAVY, pad=16)
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "bert_comparison.png", dpi=180)
    plt.close(fig)
    print("  -> bert_comparison.png")


def chart_stock_volatility():
    stocks = ["保利\n发展","恒瑞\n医药","国电\n南瑞","贵州\n茅台","海尔\n智家",
              "交通\n银行","工商\n银行","海天\n味业","海光\n信息","金山\n办公"]
    std_returns = [1.71, 2.02, 1.56, 1.27, 1.49, 1.09, 1.07, 1.30, 3.84, 2.89]
    mean_returns = [-0.126, 0.034, 0.003, -0.038, -0.085, -0.023, 0.028, -0.074, 0.276, 0.003]
    volumes = [1399, 540, 615, 368, 442, 1606, 3329, 150, 285, 64]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors_plot = [TEAL if mr > 0 else GOLD for mr in mean_returns]
    sizes_scaled = [max(s * 0.08, 32) for s in volumes]

    ax.axhline(y=0, color=GRAY, linewidth=1, linestyle="--", alpha=0.5)
    ax.axvline(x=np.mean(std_returns), color=GRAY, linewidth=1, linestyle="--", alpha=0.5)

    ax.scatter(std_returns, mean_returns, s=sizes_scaled, c=colors_plot,
               alpha=0.85, edgecolors="white", linewidth=1.5, zorder=5)

    for i, name in enumerate(stocks):
        ax.annotate(name.replace('\n',''), (std_returns[i], mean_returns[i]),
                    textcoords="offset points",
                    xytext=(0, 10 if mean_returns[i] > 0 else -15),
                    fontsize=9, ha="center", color=NAVY, fontweight="bold")

    ax.set_xlabel("Risk — Daily Return Std Dev (%)", fontsize=11, color=DARK_GRAY)
    ax.set_ylabel("Return — Mean Daily Return (%)", fontsize=11, color=DARK_GRAY)
    ax.tick_params(labelsize=9, colors=DARK_GRAY)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor=TEAL, markersize=13, label='Positive mean return'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=GOLD, markersize=13, label='Negative mean return'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor=GRAY, markersize=9, label='Bubble area = avg volume'),
    ]
    ax.legend(handles=legend_elements, fontsize=10, loc="lower right",
              frameon=True, edgecolor="#ddd", fancybox=True)
    ax.set_title("Return-Risk Profile of 10 A-Share Stocks  (2025.01 – 2026.06)",
                 fontsize=14, fontweight="bold", color=NAVY, pad=16)
    sns.despine()
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "stock_volatility.png", dpi=180)
    plt.close(fig)
    print("  -> stock_volatility.png")


def chart_lstm_comparison():
    """LSTM ablation: ts-only vs untuned-bert-fusion vs finbert-fusion (Table 9 & 11)."""
    models = ["ts-only\nLSTM", "Untuned BERT\nfusion", "FinBERT\nfusion"]
    mae7 = [7.96, 11.27, 7.54]
    mae1 = [5.10, 6.49, 4.97]
    dir_acc = [44.9, 41.8, 48.8]
    colors_bar = [GRAY, "#f59e0b", GOLD]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(models))
    width = 0.22

    b1 = ax.bar(x - width, mae7, width, color=colors_bar, edgecolor="white", linewidth=1,
                label="MAE(7-day avg)")
    b2 = ax.bar(x, mae1, width, color=[GRAY, "#f59e0b", GOLD], edgecolor="white",
                linewidth=1, alpha=0.5, label="MAE(Day 1)")
    b3 = ax.bar(x + width, dir_acc, width, color=[GRAY, "#f59e0b", GOLD], edgecolor="white",
                linewidth=1, alpha=0.25, label="Direction Acc (%)")

    for bar, val in zip(b1, mae7):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                str(val), ha="center", fontsize=10, fontweight="bold", color=NAVY)
    for bar, val in zip(b2, mae1):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                str(val), ha="center", fontsize=10, fontweight="bold", color=DARK_GRAY)
    for bar, val in zip(b3, dir_acc):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{val}%", ha="center", fontsize=10, fontweight="bold", color=DARK_GRAY)

    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=12, fontweight="bold", color=NAVY)
    ax.set_ylabel("Value", fontsize=12, color=DARK_GRAY)
    ax.legend(fontsize=10, frameon=True, edgecolor="#ddd", fancybox=True, loc="upper right")
    ax.tick_params(labelsize=10, colors=DARK_GRAY)
    ax.set_title("LSTM Ablation — 10-Stock Average  (Train 2021–2025, Test 2026)",
                 fontsize=13, fontweight="bold", color=NAVY, pad=14)
    sns.despine()
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "lstm_comparison.png", dpi=180)
    plt.close(fig)
    print("  -> lstm_comparison.png")


def chart_year_roll():
    """Year-roll experiment: MAE and Direction Accuracy by fold (Table 12)."""
    folds = ["2021\n→2022", "21–22\n→2023", "21–23\n→2024", "21–24\n→2025", "21–25\n→2026"]
    mae7_yr = [9.39, 9.88, 8.70, 10.35, 9.24]
    dir_acc_yr = [52.5, 45.0, 47.6, 50.4, 48.7]

    fig, ax1 = plt.subplots(figsize=(8.5, 4))
    x = range(len(folds))

    ax1.fill_between(x, mae7_yr, alpha=0.15, color=GOLD)
    ax1.plot(x, mae7_yr, color=GOLD, linewidth=2.2, marker="o", markersize=8,
             markerfacecolor="white", markeredgecolor=GOLD, markeredgewidth=2,
             label="MAE(7-day avg)")
    ax1.set_ylabel("MAE(7-day avg)", fontsize=11, color=GOLD, fontweight="bold")
    ax1.tick_params(axis='y', labelcolor=GOLD, labelsize=9)
    for i, (xi, v) in enumerate(zip(x, mae7_yr)):
        ax1.annotate(str(v), (xi, v), textcoords="offset points", xytext=(0, -18),
                     fontsize=9, ha="center", color=GOLD, fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot(x, dir_acc_yr, color=TEAL, linewidth=2.2, marker="s", markersize=7,
             markerfacecolor="white", markeredgecolor=TEAL, markeredgewidth=2,
             label="Direction Acc")
    ax2.set_ylabel("Direction Accuracy (%)", fontsize=11, color=TEAL, fontweight="bold")
    ax2.tick_params(axis='y', labelcolor=TEAL, labelsize=9)
    for i, (xi, v) in enumerate(zip(x, dir_acc_yr)):
        ax2.annotate(f"{v}%", (xi, v), textcoords="offset points", xytext=(0, 14),
                     fontsize=9, ha="center", color=TEAL, fontweight="bold")

    ax1.set_xticks(x)
    ax1.set_xticklabels(folds, fontsize=11, color=NAVY, fontweight="bold")
    ax1.tick_params(axis='x', colors=DARK_GRAY)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, frameon=True,
               edgecolor="#ddd", fancybox=True, loc="upper center",
               bbox_to_anchor=(0.5, -0.12), ncol=2)

    ax1.set_title("Year-Roll Experiment — FinBERT Fusion  (Increasing Training Data)",
                  fontsize=13, fontweight="bold", color=NAVY, pad=14)
    sns.despine(right=False)
    fig.tight_layout(pad=0.8)
    fig.savefig(OUT / "year_roll.png", dpi=180)
    plt.close(fig)
    print("  -> year_roll.png")


if __name__ == "__main__":
    print(f"Generating charts into {OUT}/ ...")
    chart_price_trends()
    chart_news_distribution()
    chart_bert_comparison()
    chart_stock_volatility()
    chart_lstm_comparison()
    chart_year_roll()
    print("Done.")
