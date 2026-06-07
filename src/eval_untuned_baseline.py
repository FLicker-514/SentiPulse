"""
Evaluate untuned BERT (random classifier head) on the FinFE test set.
Compares against the fine-tuned model baseline.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from datasets import ClassLabel, Dataset, DatasetDict
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
    set_seed,
)

MODEL_PATH = "models/bert-base-chinese"
DATA_DIR = "data"
OUTPUT_DIR = "outputs/bert-untuned-baseline"
SEED = 42


def load_local_parquet(data_dir: str) -> DatasetDict:
    train_path = Path(data_dir) / "train-00000-of-00001.parquet"
    test_path = Path(data_dir) / "test-00000-of-00001.parquet"
    return DatasetDict({
        "train": Dataset.from_parquet(str(train_path)),
        "test": Dataset.from_parquet(str(test_path)),
    })


def main() -> None:
    set_seed(SEED)

    # Load data
    raw_dataset = load_local_parquet(DATA_DIR)
    label_names = sorted({str(ex["label"]) for ex in raw_dataset["train"]})
    label_to_id = {name: idx for idx, name in enumerate(label_names)}
    id_to_label = {idx: name for name, idx in label_to_id.items()}

    # Cast label column to ClassLabel for stratify
    train_ds = raw_dataset["train"].cast_column("label", ClassLabel(names=label_names))
    test_ds = raw_dataset["test"].cast_column("label", ClassLabel(names=label_names))

    # Use the same train/validation split as training
    train_valid = train_ds.train_test_split(test_size=0.1, seed=SEED, stratify_by_column="label")

    def convert_label(example: dict) -> dict:
        example["labels"] = int(example["label"])
        return example

    for split in train_valid:
        train_valid[split] = train_valid[split].map(convert_label)
    test_ds = test_ds.map(convert_label)

    dataset = DatasetDict({
        "train": train_valid["train"],
        "validation": train_valid["test"],
        "test": test_ds,
    })

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

    def tokenize(batch: dict) -> dict:
        return tokenizer(batch["sentence"], truncation=True, max_length=256)

    remove_cols = [c for c in dataset["train"].column_names if c != "labels"]
    tokenized = {}
    for split in dataset:
        tokenized[split] = dataset[split].map(tokenize, batched=True, remove_columns=remove_cols)

    # Load UNTUNED model (fresh random classifier head)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_PATH,
        num_labels=len(label_names),
        id2label=id_to_label,
        label2id=label_to_id,
    )

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

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_eval_batch_size=32,
        seed=SEED,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
    )

    # Evaluate on validation set
    print("=== Untuned BERT (random classifier head) ===")
    val_metrics = trainer.evaluate(eval_dataset=tokenized["validation"])
    print(json.dumps(val_metrics, indent=2))

    # Evaluate on test set
    test_metrics = trainer.evaluate(eval_dataset=tokenized["test"], metric_key_prefix="test")
    print(json.dumps(test_metrics, indent=2))

    # Save
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(OUTPUT_DIR, "val_metrics.json").write_text(json.dumps(val_metrics, indent=2, ensure_ascii=False))
    Path(OUTPUT_DIR, "test_metrics.json").write_text(json.dumps(test_metrics, indent=2, ensure_ascii=False))

    # Comparison
    print("\n=== Comparison ===")
    ft_test = json.loads(Path("outputs/bert-financial-sentiment/test_metrics.json").read_text())
    print(f"{'Metric':<20} {'Untuned':>10} {'Fine-tuned':>12}")
    print("-" * 44)
    for key in ["test_accuracy", "test_macro_f1", "test_weighted_f1"]:
        print(f"{key:<20} {test_metrics.get(key, 0):>10.4f} {ft_test.get(key, 0):>12.4f}")


if __name__ == "__main__":
    main()
