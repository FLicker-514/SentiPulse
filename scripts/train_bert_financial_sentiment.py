#!/usr/bin/env python3
"""
在 SentiPulse 内微调 FinBERT2-large（或 BERT）金融情感分类模型（可选）。

默认基座：../models/FinBERT2-large
默认输出：data/models/finbert2-sentiment/best_model

示例（服务器只需 SentiPulse-1 目录）：

  cd SentiPulse
  export HF_ENDPOINT=https://hf-mirror.com
  python scripts/train_bert_financial_sentiment.py

  export SENTIMENT_MODEL_PATH=data/models/finbert2-sentiment/best_model
  python scripts/build_sentiment_both.py --variant finbert --dataset CSMD50_merged
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from datasets import ClassLabel, Dataset, DatasetDict, load_dataset
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_MODELS = ROOT.parent / "models"
DEFAULT_MODEL = EXTERNAL_MODELS / "FinBERT2-large"
DEFAULT_OUTPUT = ROOT / "data" / "models" / "finbert2-sentiment"
LOCAL_DATA_DIR = ROOT / "data" / "finfe"

LABEL_ALIASES = {
    "negative": "negative",
    "neutral": "neutral",
    "positive": "positive",
    "负面": "negative",
    "中性": "neutral",
    "正面": "positive",
    "消极": "negative",
    "积极": "positive",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune FinBERT2-large / BERT for financial sentiment (SentiPulse-1)."
    )
    parser.add_argument(
        "--dataset-name",
        default="FinanceMTEB/FinFE",
        help="HuggingFace 数据集名，或本地目录 data/finfe（含 parquet）",
    )
    parser.add_argument(
        "--model-name",
        default=str(DEFAULT_MODEL),
        help=f"预训练基座路径，默认 {DEFAULT_MODEL}",
    )
    parser.add_argument("--text-column", default="sentence")
    parser.add_argument("--label-column", default="label")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT),
        help=f"微调输出目录，best_model 保存在其下，默认 {DEFAULT_OUTPUT}",
    )
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--num-train-epochs", type=float, default=3.0)
    parser.add_argument("--per-device-train-batch-size", type=int, default=4)
    parser.add_argument("--per-device-eval-batch-size", type=int, default=8)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-size", type=float, default=0.1)
    return parser.parse_args()


def normalize_label(value: object) -> str | int:
    if isinstance(value, str):
        return LABEL_ALIASES.get(value.strip(), value.strip())
    return int(value)


def prepare_splits(raw_dataset: DatasetDict, validation_size: float, seed: int) -> DatasetDict:
    if "validation" in raw_dataset:
        return raw_dataset

    if "test" in raw_dataset and "train" in raw_dataset:
        train_ds = raw_dataset["train"]
        if train_ds.features["label"].dtype.startswith("int"):
            label_names = sorted({str(ex["label"]) for ex in train_ds})
            train_ds = train_ds.cast_column("label", ClassLabel(names=label_names))
        train_valid = train_ds.train_test_split(test_size=validation_size, seed=seed, stratify_by_column="label")
        return DatasetDict(
            {
                "train": train_valid["train"],
                "validation": train_valid["test"],
                "test": raw_dataset["test"].cast_column("label", ClassLabel(names=label_names)),
            }
        )

    if "train" not in raw_dataset:
        raise ValueError("Dataset must contain a train split.")

    train_ds = raw_dataset["train"]
    if train_ds.features["label"].dtype.startswith("int"):
        label_names = sorted({str(ex["label"]) for ex in train_ds})
        train_ds = train_ds.cast_column("label", ClassLabel(names=label_names))
    train_valid = train_ds.train_test_split(test_size=validation_size, seed=seed, stratify_by_column="label")
    return DatasetDict({"train": train_valid["train"], "validation": train_valid["test"]})


def encode_labels(dataset: DatasetDict, label_column: str) -> tuple[DatasetDict, list[str]]:
    raw_labels = [normalize_label(example[label_column]) for example in dataset["train"]]
    label_names = sorted({str(label) for label in raw_labels})
    label_to_id = {label: index for index, label in enumerate(label_names)}

    def convert_label(example: dict) -> dict:
        normalized = str(normalize_label(example[label_column]))
        example["labels"] = label_to_id[normalized]
        return example

    return dataset.map(convert_label), label_names


def compute_metrics(eval_pred: tuple[np.ndarray, np.ndarray]) -> dict[str, float]:
    logits, labels = eval_pred
    predictions = np.argmax(logits, axis=-1)
    precision, recall, macro_f1, _ = precision_recall_fscore_support(
        labels, predictions, average="macro", zero_division=0
    )
    return {
        "accuracy": accuracy_score(labels, predictions),
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": macro_f1,
        "weighted_f1": f1_score(labels, predictions, average="weighted"),
    }


def load_local_parquet(data_dir: Path) -> DatasetDict:
    train_path = data_dir / "train-00000-of-00001.parquet"
    test_path = data_dir / "test-00000-of-00001.parquet"
    if not train_path.exists():
        raise FileNotFoundError(f"Training parquet not found at {train_path}")
    if not test_path.exists():
        raise FileNotFoundError(f"Test parquet not found at {test_path}")
    return DatasetDict({
        "train": Dataset.from_parquet(str(train_path)),
        "test": Dataset.from_parquet(str(test_path)),
    })


def resolve_dataset(dataset_name: str) -> DatasetDict:
    if dataset_name in ("data/finfe", "finfe") or Path(dataset_name) == LOCAL_DATA_DIR:
        return load_local_parquet(LOCAL_DATA_DIR)
    p = Path(dataset_name)
    if p.is_dir():
        return load_local_parquet(p)
    return load_dataset(dataset_name)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    model_path = Path(args.model_name).expanduser()
    if not model_path.is_dir():
        print(f"❌ 未找到基座模型: {model_path}", file=sys.stderr)
        print("   请将 FinBERT2-large 放到 ../models/FinBERT2-large", file=sys.stderr)
        sys.exit(1)

    print(f"基座模型: {model_path}")
    print(f"输出目录: {args.output_dir}")

    raw_dataset = resolve_dataset(args.dataset_name)
    dataset = prepare_splits(raw_dataset, args.validation_size, args.seed)
    dataset, label_names = encode_labels(dataset, args.label_column)

    tokenizer = AutoTokenizer.from_pretrained(str(model_path))

    def tokenize(batch: dict) -> dict:
        return tokenizer(batch[args.text_column], truncation=True, max_length=args.max_length)

    remove_columns = [column for column in dataset["train"].column_names if column != "labels"]
    tokenized_dataset = dataset.map(tokenize, batched=True, remove_columns=remove_columns)

    id_to_label = {index: label for index, label in enumerate(label_names)}
    label_to_id = {label: index for index, label in id_to_label.items()}

    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path),
        num_labels=len(label_names),
        id2label=id_to_label,
        label2id=label_to_id,
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        num_train_epochs=args.num_train_epochs,
        weight_decay=args.weight_decay,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_steps=50,
        report_to="none",
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["validation"],
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    trainer.train()
    eval_metrics = trainer.evaluate()

    output_dir = Path(args.output_dir)
    best_dir = output_dir / "best_model"
    trainer.save_model(best_dir)
    tokenizer.save_pretrained(best_dir)

    (output_dir / "eval_metrics.json").write_text(
        json.dumps(eval_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "labels.json").write_text(
        json.dumps(label_to_id, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if "test" in tokenized_dataset:
        test_metrics = trainer.evaluate(tokenized_dataset["test"], metric_key_prefix="test")
        (output_dir / "test_metrics.json").write_text(
            json.dumps(test_metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"\n✅ 微调完成，模型已保存: {best_dir.resolve()}")
    print("下一步:")
    print(f'  export SENTIMENT_MODEL_PATH="{best_dir.resolve()}"')
    print("  python scripts/build_sentiment_both.py --variant finbert --dataset CSMD50_merged --force")


if __name__ == "__main__":
    main()
