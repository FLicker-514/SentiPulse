@echo off
setlocal

set HF_ENDPOINT=https://hf-mirror.com

uv run python src\train_bert_financial_sentiment.py ^
  --dataset-name data ^
  --model-name models\bert-base-chinese ^
  --output-dir outputs\bert-financial-sentiment

endlocal
