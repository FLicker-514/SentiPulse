"""延迟加载 TensorFlow，便于 FinBERT 环境仅做情感推理时不强依赖 TF。"""

_TF = None
_TF_ERROR = None


def get_tensorflow():
    global _TF, _TF_ERROR
    if _TF is not None:
        return _TF
    try:
        import tensorflow as tf

        _TF = tf
        return tf
    except ImportError as e:
        _TF_ERROR = e
        raise ImportError(
            "预测/训练 LSTM 需要 TensorFlow。请在当前环境中安装：\n"
            "  pip install \"tensorflow>=2.15\" pandas scikit-learn joblib\n"
            "或：pip install -r requirements.txt\n"
            "（build-sentiment / test-sentiment 仅需 torch+transformers，无需 tensorflow）"
        ) from e
