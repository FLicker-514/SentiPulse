#!/usr/bin/env python3
"""SentiPulse CLI：理论在 theory/，应用在 application/，数据在 data/。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def cmd_setup_data(args):
    cmd = [sys.executable, "-m", "theory.data_cleaning.setup_csmd"]
    if args.dataset:
        cmd.extend(["--dataset", args.dataset])
    if args.stocks:
        cmd.extend(["--stocks", *args.stocks])
    if args.rebuild:
        cmd.append("--rebuild")
    if args.source:
        cmd.extend(["--source", args.source])
    subprocess.check_call(cmd, cwd=ROOT)


def cmd_crawl_news(args):
    try:
        import bs4  # noqa: F401
        import selenium  # noqa: F401
    except ImportError:
        print(
            "缺少爬虫依赖，请先执行：\n"
            "  pip install beautifulsoup4 selenium\n"
            "或：pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)
    cmd = [
        sys.executable,
        "-m",
        "theory.data_crawler.news_scraper",
        "--max-articles",
        str(args.max_articles),
        "--max-scroll",
        str(args.max_scroll),
    ]
    if args.symbols:
        cmd.extend(["--symbols", *args.symbols])
    if args.links_only:
        cmd.append("--links-only")
    if args.no_headless:
        cmd.append("--no-headless")
    if args.force:
        cmd.append("--force")
    if args.no_export:
        cmd.append("--no-export")
    if getattr(args, "output_dir", None):
        cmd.extend(["--output-dir", args.output_dir])
    if getattr(args, "ticker", None):
        cmd.extend(["--ticker", *args.ticker])
    if getattr(args, "chrome_binary", None):
        cmd.extend(["--chrome-binary", args.chrome_binary])
    if getattr(args, "chromedriver", None):
        cmd.extend(["--chromedriver", args.chromedriver])
    subprocess.check_call(cmd, cwd=ROOT)


def cmd_train_sentiment(args):
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "train_bert_financial_sentiment.py"),
        "--dataset-name",
        args.dataset_name,
        "--model-name",
        args.model_name,
        "--output-dir",
        args.output_dir,
        "--num-train-epochs",
        str(args.epochs),
        "--per-device-train-batch-size",
        str(args.batch_size),
        "--per-device-eval-batch-size",
        str(args.eval_batch_size),
        "--max-length",
        str(args.max_length),
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def cmd_build_sentiment(args):
    from theory.price_forecast.sentiment_features import build_daily_sentiment, news_root_for_dataset

    news_root = news_root_for_dataset(args.dataset) if args.dataset else None
    variants = ["bert", "finbert"] if args.variant == "both" else [args.variant]
    for v in variants:
        print(f"\n========== build-sentiment: {v} ==========")
        build_daily_sentiment(
            symbols=args.symbols,
            force=args.force,
            variant=v,
            news_root=news_root,
        )


def cmd_train(args):
    cmd = [
        sys.executable,
        "-m",
        "theory.price_forecast.train",
        "--mode",
        args.mode,
        "--epochs",
        str(args.epochs),
    ]
    if args.symbols:
        cmd.extend(["--symbols", *args.symbols])
    if args.rebuild_sentiment:
        cmd.append("--rebuild-sentiment")
    if getattr(args, "train_end", None):
        cmd.extend(["--train-end", args.train_end])
    if getattr(args, "dataset", None):
        cmd.extend(["--dataset", args.dataset])
    subprocess.check_call(cmd, cwd=ROOT)


def cmd_evaluate(args):
    from theory.price_forecast.evaluate import format_backtest_text, run_evaluate

    report = run_evaluate(
        args.symbol,
        mode=args.mode,
        n_points=args.n_points,
        test_start=getattr(args, "test_start", None),
    )
    print(format_backtest_text(report), flush=True)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_predict(args):
    from theory.price_forecast.pipeline import format_comparison_text, run_prediction

    result = run_prediction(
        args.symbol,
        mode=args.mode,
        news_text=args.news,
        use_news_api=not args.no_news_api,
    )
    if args.mode == "both" and "comparison" in result:
        print(format_comparison_text(result["comparison"]), flush=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_list_symbols(_args):
    from theory.data_cleaning.symbols import default_price_dir, list_symbols_from_data

    for s in list_symbols_from_data(default_price_dir()):
        print(s)


def cmd_list_models(args):
    from theory.shared.paths import ALL_TRAIN_MODES, MODELS_DIR, model_paths

    if not MODELS_DIR.exists():
        print("(空) data/models/")
        return
    print("已有权重文件:")
    for p in sorted(MODELS_DIR.glob("*")):
        if p.suffix in (".h5", ".pkl", ".json"):
            print(f"  {p.name}")
    if args.symbol:
        sym = args.symbol.strip()
        for mode in ALL_TRAIN_MODES:
            mp, sp = model_paths(sym, mode)
            ok = mp.exists() and sp.exists()
            print(f"  {sym} [{mode}]: {'OK' if ok else '缺失'} -> {mp.name}")


def cmd_year_roll_experiment(args):
    from theory.price_forecast.year_roll_experiment import run_year_roll_experiment

    run_year_roll_experiment(
        symbols=args.symbols,
        epochs=args.epochs,
        first_train_year=args.first_train_year,
        last_test_year=args.last_test_year,
        verbose=args.verbose,
    )


def cmd_compare_sentiment(args):
    from theory.price_forecast.sentiment_features import news_root_for_dataset
    from theory.sentiment_model.compare_sentiment import compare_sentiment_models

    news_root = news_root_for_dataset(args.dataset) if args.dataset else None
    report = compare_sentiment_models(
        n=args.count,
        symbol=args.symbol,
        seed=args.seed,
        news_root=news_root,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


def cmd_test_sentiment(args):
    from theory.sentiment_model.sample_news import run_sentiment_batch

    rows = run_sentiment_batch(
        n=args.count,
        symbol=args.symbol,
        seed=args.seed,
    )
    print(json.dumps({"sampled": len(rows), "seed": args.seed, "results": rows}, indent=2, ensure_ascii=False))


def cmd_serve(args):
    from application.backend.app import app

    app.run(host=args.host, port=args.port, debug=args.debug)


def main():
    parser = argparse.ArgumentParser(description="SentiPulse · 舆情脉动")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("setup-data", "import-lightquant"):
        p = sub.add_parser(name, help="（2）清洗：生成 data/processed 下训练文件")
        p.add_argument("--dataset", default="CSMD50")
        p.add_argument("--stocks", nargs="+")
        p.add_argument("--rebuild", action="store_true")
        p.add_argument("--source", default=None, help="外部 LightQuant/dataset/CSMD50 路径")

    p_crawl = sub.add_parser("crawl-news", help="（1）证券时报爬虫 -> data/processed/CSMD50/news")
    p_crawl.add_argument("--symbols", nargs="+", help="股票中文名，如 贵州茅台")
    p_crawl.add_argument(
        "--ticker",
        nargs="+",
        help="股票代码，与 --symbols 对应，如 sh.600519（无 CSMD50.csv 时必填）",
    )
    p_crawl.add_argument("--max-articles", type=int, default=20, help="每只股票最多抓正文数（试跑 10~30）")
    p_crawl.add_argument("--max-scroll", type=int, default=15, help="列表页滚动次数")
    p_crawl.add_argument("--links-only", action="store_true")
    p_crawl.add_argument("--no-headless", action="store_true", help="显示浏览器（调试）")
    p_crawl.add_argument("--force", action="store_true", help="忽略缓存重新爬")
    p_crawl.add_argument("--no-export", action="store_true")
    p_crawl.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="输出根目录（下含 news_link/ news_raw/ news/）",
    )
    p_crawl.add_argument("--chrome-binary", default=None, help="Chromium/Chrome 路径")
    p_crawl.add_argument("--chromedriver", default=None, help="chromedriver 路径")

    p_ft = sub.add_parser(
        "train-sentiment",
        help="（可选）微调 FinBERT2-large；默认流程无需此步骤，直接用预训练权重",
    )
    p_ft.add_argument(
        "--model-name",
        default=str(ROOT.parent / "models" / "FinBERT2-large"),
        help="预训练基座，默认 ../models/FinBERT2-large",
    )
    p_ft.add_argument(
        "--dataset-name",
        default="FinanceMTEB/FinFE",
        help="训练数据集，默认 FinanceMTEB/FinFE",
    )
    p_ft.add_argument(
        "--output-dir",
        default=str(ROOT / "data" / "models" / "finbert2-sentiment"),
        help="微调输出目录",
    )
    p_ft.add_argument("--epochs", type=float, default=3.0)
    p_ft.add_argument("--batch-size", type=int, default=4, help="训练 batch size")
    p_ft.add_argument("--eval-batch-size", type=int, default=8)
    p_ft.add_argument("--max-length", type=int, default=256)

    p_sent_build = sub.add_parser("build-sentiment", help="（3b）Bert/FinBERT2 生成日度情感特征 CSV")
    p_sent_build.add_argument("--symbols", nargs="+")
    p_sent_build.add_argument("--force", action="store_true", help="覆盖已有情感 CSV")
    p_sent_build.add_argument(
        "--variant",
        choices=["bert", "finbert", "both"],
        default="both",
        help="bert=未微调Bert; finbert=FinBERT2-large预训练; both=两者都生成",
    )
    p_sent_build.add_argument(
        "--dataset",
        default="CSMD50_merged",
        help="新闻来源 data/processed/<dataset>/news，默认 CSMD50_merged",
    )

    p_train = sub.add_parser("train", help="（4）训练 ts-only / fusion-bert / fusion LSTM")
    p_train.add_argument(
        "--mode",
        choices=["ts-only", "fusion-bert", "fusion", "all"],
        default="ts-only",
        help="ts-only | fusion-bert(未微调Bert) | fusion(FinBERT2-large) | all(三组全训)",
    )
    p_train.add_argument(
        "--dataset",
        default="CSMD50_merged",
        help="融合训练时新闻目录 data/processed/<dataset>/news",
    )
    p_train.add_argument("--symbols", nargs="+")
    p_train.add_argument("--epochs", type=int, default=10)
    p_train.add_argument("--rebuild-sentiment", action="store_true")
    p_train.add_argument(
        "--train-end",
        default="2024-01-01",
        help="训练截止日（不含），默认 2024-01-01；2024 及以后留作测试",
    )

    p_eval = sub.add_parser("evaluate", help="（4）回测：2024 测试集与真实价格对比")
    p_eval.add_argument("--symbol", required=True)
    p_eval.add_argument(
        "--mode",
        choices=["ts-only", "fusion-bert", "fusion", "both", "all"],
        default="all",
        help="all=三组对比回测（默认）",
    )
    p_eval.add_argument(
        "--n-points",
        type=int,
        default=40,
        help="回测截面数量（在 2024 测试集内取样，默认40）",
    )
    p_eval.add_argument(
        "--test-start",
        default="2024-01-01",
        help="测试集起始日（含），默认 2024-01-01",
    )

    p_pred = sub.add_parser("predict", help="（4）股价预测（未来，无真实值对比）")
    p_pred.add_argument("--symbol", required=True)
    p_pred.add_argument(
        "--mode",
        choices=["ts-only", "fusion-bert", "fusion", "both", "all"],
        default="all",
        help="all=同时输出三组模型",
    )
    p_pred.add_argument("--news", default=None)
    p_pred.add_argument("--no-news-api", action="store_true")

    sub.add_parser("list-symbols", help="列出 data/processed/CSMD50 中的股票")

    p_models = sub.add_parser("list-models", help="查看 data/models 下已训练权重")
    p_models.add_argument("--symbol", default=None, help="检查某只股票 ts-only/fusion 是否齐全")

    p_sent = sub.add_parser("test-sentiment", help="从 CSMD 新闻随机抽样测试 FinBERT")
    p_sent.add_argument("-n", "--count", type=int, default=10, help="抽样条数（默认 10）")
    p_sent.add_argument("--symbol", default=None, help="仅抽某只股票，如 贵州茅台")
    p_sent.add_argument("--seed", type=int, default=None, help="随机种子，便于复现")

    p_yr = sub.add_parser(
        "year-roll-experiment",
        help="（5）FinBERT fusion 累积训练窗实验：考察训练数据量对预测的影响（全股票）",
    )
    p_yr.add_argument("--symbols", nargs="+", help="默认全部股票")
    p_yr.add_argument("--epochs", type=int, default=20)
    p_yr.add_argument("--first-train-year", type=int, default=2021)
    p_yr.add_argument("--last-test-year", type=int, default=None)
    p_yr.add_argument("--verbose", type=int, default=0)

    p_cmp = sub.add_parser(
        "compare-sentiment",
        help="对比 Bert vs FinBERT2-large 在同一批新闻上的情感判断差异",
    )
    p_cmp.add_argument("-n", "--count", type=int, default=50)
    p_cmp.add_argument("--symbol", default=None)
    p_cmp.add_argument("--seed", type=int, default=42)
    p_cmp.add_argument("--dataset", default="CSMD50_merged")

    p_serve = sub.add_parser("serve", help="启动 application 后端 API")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=5000)
    p_serve.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    handlers = {
        "setup-data": cmd_setup_data,
        "import-lightquant": cmd_setup_data,
        "crawl-news": cmd_crawl_news,
        "train-sentiment": cmd_train_sentiment,
        "build-sentiment": cmd_build_sentiment,
        "train": cmd_train,
        "evaluate": cmd_evaluate,
        "predict": cmd_predict,
        "list-symbols": cmd_list_symbols,
        "list-models": cmd_list_models,
        "test-sentiment": cmd_test_sentiment,
        "year-roll-experiment": cmd_year_roll_experiment,
        "compare-sentiment": cmd_compare_sentiment,
        "serve": cmd_serve,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
