"""Flask API（调用 theory 模块）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, request
from flask_cors import CORS

from theory.price_forecast.pipeline import list_available_symbols, run_prediction
from theory.sentiment_model.inference import analyze_sentiment, sentiment_probabilities

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "project": "SentiPulse"})


@app.route("/symbols", methods=["GET"])
def symbols():
    try:
        return jsonify({"symbols": list_available_symbols()})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/sentiment", methods=["POST"])
def sentiment():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "请提供 text 字段"}), 400
    return jsonify(
        {
            "probabilities": sentiment_probabilities(text),
            "result": analyze_sentiment(text),
        }
    )


@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or {}
    symbol = data.get("symbol", "")
    if not symbol:
        return jsonify({"error": "请提供 symbol 字段"}), 400
    try:
        return jsonify(
            run_prediction(
                symbol=symbol,
                news_text=data.get("news_text"),
                use_news_api=data.get("use_news_api", True),
            )
        )
    except (FileNotFoundError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"预测失败: {e}"}), 500


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
