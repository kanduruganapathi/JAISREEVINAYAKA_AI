from __future__ import annotations

from app.models.analysis import Candle
from app.models.strategy import StrategyRule
from app.services.indicators import compute_indicator_pack
from app.services.smc import detect_market_structure


def _ema_last(values: list[float], period: int) -> float | None:
    if period <= 0 or len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    out = values[0]
    for v in values[1:]:
        out = alpha * v + (1.0 - alpha) * out
    return out


class StrategyEngine:
    @staticmethod
    def _param_float(
        rule: StrategyRule,
        key: str,
        default: float,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> float:
        raw = rule.params.get(key, default)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = default
        if min_value is not None:
            val = max(min_value, val)
        if max_value is not None:
            val = min(max_value, val)
        return val

    @staticmethod
    def _param_int(
        rule: StrategyRule,
        key: str,
        default: int,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        raw = rule.params.get(key, default)
        try:
            val = int(float(raw))
        except (TypeError, ValueError):
            val = default
        if min_value is not None:
            val = max(min_value, val)
        if max_value is not None:
            val = min(max_value, val)
        return val

    def generate_signal(self, candles: list[Candle], rule: StrategyRule) -> str:
        if len(candles) < 60:
            return "flat"

        indicators = compute_indicator_pack(candles)
        smc = detect_market_structure(candles)
        closes = [c.close for c in candles]
        last = closes[-1]

        if rule.name == "ema_cross":
            fast_ema_period = self._param_int(rule, "fast_ema", 20, min_value=5, max_value=120)
            slow_ema_period = self._param_int(rule, "slow_ema", 50, min_value=10, max_value=240)
            if fast_ema_period >= slow_ema_period:
                slow_ema_period = fast_ema_period + 5

            fast_ema = _ema_last(closes, fast_ema_period)
            slow_ema = _ema_last(closes, slow_ema_period)
            if fast_ema is None or slow_ema is None:
                return "flat"

            require_price_confirm = (
                self._param_int(rule, "confirm_price_above_ema", 1, min_value=0, max_value=1) == 1
            )
            min_gap_bps = self._param_float(rule, "trend_gap_bps", 0.0, min_value=0.0, max_value=200.0)
            gap_bps = abs(fast_ema - slow_ema) / max(last, 1e-9) * 10000.0
            if gap_bps < min_gap_bps:
                return "flat"

            if fast_ema > slow_ema and (not require_price_confirm or last > fast_ema):
                return "long"
            if fast_ema < slow_ema and (not require_price_confirm or last < fast_ema):
                return "short"
            return "flat"

        if rule.name == "rsi_reversion":
            rsi = indicators["rsi_14"]
            oversold = self._param_float(rule, "oversold", 30.0, min_value=5.0, max_value=50.0)
            overbought = self._param_float(rule, "overbought", 70.0, min_value=50.0, max_value=95.0)
            exit_rsi = self._param_float(rule, "exit_rsi", 50.0, min_value=20.0, max_value=80.0)
            neutral_band = self._param_float(rule, "neutral_band", 4.0, min_value=0.5, max_value=15.0)
            if rsi <= oversold:
                return "long"
            if rsi >= overbought:
                return "short"
            if abs(rsi - exit_rsi) <= neutral_band:
                return "flat"
            return "flat"

        if rule.name == "multi_timeframe_breakout":
            lookback = self._param_int(rule, "breakout_lookback", 20, min_value=10, max_value=120)
            buffer_bps = self._param_float(rule, "breakout_buffer_bps", 0.0, min_value=0.0, max_value=60.0)
            if len(candles) < lookback + 1:
                return "flat"
            high_lookback = max(c.high for c in candles[-lookback:])
            low_lookback = min(c.low for c in candles[-lookback:])
            up_trigger = high_lookback * (1 + buffer_bps / 10000.0)
            down_trigger = low_lookback * (1 - buffer_bps / 10000.0)

            if last >= up_trigger:
                return "long"
            if last <= down_trigger:
                return "short"
            return "flat"

        # smc_breakout
        bull_rsi_min = self._param_float(rule, "bull_rsi_min", 48.0, min_value=20.0, max_value=80.0)
        bear_rsi_max = self._param_float(rule, "bear_rsi_max", 52.0, min_value=20.0, max_value=80.0)
        require_displacement = (
            self._param_int(rule, "require_displacement", 1, min_value=0, max_value=1) == 1
        )
        min_hist = self._param_float(rule, "min_histogram_strength", 0.01, min_value=0.0, max_value=10.0)
        rsi = indicators["rsi_14"]
        hist = indicators["histogram"]

        bullish_displacement = not require_displacement or hist >= min_hist
        bearish_displacement = not require_displacement or hist <= -min_hist

        if (
            smc["bos"] == "bullish_bos"
            and smc["trend"] == "uptrend"
            and rsi >= bull_rsi_min
            and bullish_displacement
        ):
            return "long"
        if (
            smc["bos"] == "bearish_bos"
            and smc["trend"] == "downtrend"
            and rsi <= bear_rsi_max
            and bearish_displacement
        ):
            return "short"
        return "flat"
