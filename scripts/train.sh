#!/usr/bin/env bash
set -euo pipefail

python src/train_bert_financial_sentiment.py \
  --dataset-name FinanceMTEB/FinFE \
  --model-name bert-base-chinese \
  --output-dir outputs/bert-financial-sentiment
