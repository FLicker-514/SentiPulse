# 后端 API

`app.py`：Flask 服务，封装 `theory.price_forecast` 与 `theory.sentiment_model`。

```bash
# 从项目根目录启动
python application/backend/app.py
# 或
python run.py serve
```

端点：`/health`、`/symbols`、`/sentiment`、`/predict`
