from __future__ import annotations

import math

import numpy as np

from app.models.analysis import Candle


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.array([])
    alpha = 2 / (period + 1)
    out = np.zeros_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def _rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    if len(values) < period + 1:
        return np.array([])

    deltas = np.diff(values)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.zeros_like(values)
    avg_loss = np.zeros_like(values)

    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, len(values)):
        avg_gain[i] = ((avg_gain[i - 1] * (period - 1)) + gains[i - 1]) / period
        avg_loss[i] = ((avg_loss[i - 1] * (period - 1)) + losses[i - 1]) / period

    rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0

    tr_values = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    return float(np.mean(tr_values[-period:]))


def compute_indicator_pack(candles: list[Candle]) -> dict:
    closes = np.array([c.close for c in candles], dtype=float)
    if len(closes) < 30:
        return {
            "ema_20": 0.0,
            "ema_50": 0.0,
            "rsi_14": 0.0,
            "macd": 0.0,
            "signal": 0.0,
            "histogram": 0.0,
            "atr_14": 0.0,
            "volatility": 0.0,
        }

    ema_20 = _ema(closes, 20)
    ema_50 = _ema(closes, 50)
    ema_12 = _ema(closes, 12)
    ema_26 = _ema(closes, 26)
    macd_line = ema_12 - ema_26
    signal_line = _ema(macd_line, 9)
    rsi_14 = _rsi(closes, 14)

    returns = np.diff(closes) / closes[:-1]
    volatility = float(np.std(returns[-50:]) * math.sqrt(252)) if len(returns) >= 50 else 0.0

    return {
        "ema_20": float(ema_20[-1]),
        "ema_50": float(ema_50[-1]),
        "rsi_14": float(rsi_14[-1]) if len(rsi_14) else 0.0,
        "macd": float(macd_line[-1]),
        "signal": float(signal_line[-1]) if len(signal_line) else 0.0,
        "histogram": float(macd_line[-1] - signal_line[-1]) if len(signal_line) else 0.0,
        "atr_14": _atr(candles, 14),
        "volatility": volatility,
    }
