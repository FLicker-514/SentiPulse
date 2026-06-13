"""LSTM 模型构建。"""

from theory.price_forecast.tf_backend import get_tensorflow
from theory.shared.paths import SEQ_LENGTH


def build_lstm(n_features: int, seq_length: int = SEQ_LENGTH):
    tf = get_tensorflow()
    LSTM = tf.keras.layers.LSTM
    Dense = tf.keras.layers.Dense
    Dropout = tf.keras.layers.Dropout
    Sequential = tf.keras.models.Sequential
    model = Sequential([
        LSTM(100, return_sequences=True, input_shape=(seq_length, n_features)),
        Dropout(0.2),
        LSTM(100, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1),
    ])
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model
