# （2）数据清洗 + 蒸馏

## 清洗 `setup_csmd.py`

- 从 `../LightQuant/dataset/CSMD50`（可选）复制 → `data/processed/CSMD50/`
- 生成 → `data/processed/datasets/`、`CSMD_cleaned.csv`、`csmd_news.json`

```bash
python run.py setup-data
python run.py setup-data --rebuild   # 已复制过，仅重建 processed
```

## 蒸馏 `llm_distill.py`

LightQuant LLM 因子抽取（vLLM），可选。
