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

    @staticmethod
    def _volume_ratio(candles: list[Candle], lookback: int = 30) -> float:
        if len(candles) < lookback + 2:
            return 1.0
        recent = candles[-1].volume
        baseline = sum(c.volume for c in candles[-(lookback + 1) : -1]) / lookback
        return recent / max(baseline, 1e-9)

    @staticmethod
    def _body_atr_ratio(candles: list[Candle], atr: float) -> float:
        if not candles:
            return 0.0
        body = abs(candles[-1].close - candles[-1].open)
        return body / max(atr, 1e-9)

    @staticmethod
    def _in_price_zone(price: float, zone: dict | None) -> bool:
        if not isinstance(zone, dict):
            return False
        lo = float(zone.get("from", 0.0))
        hi = float(zone.get("to", 0.0))
        low, high = (lo, hi) if lo <= hi else (hi, lo)
        return low <= price <= high

    @staticmethod
    def _in_any_zone(
        price: float,
        zones: list[dict],
        allowed_types: set[str],
        min_index: int,
    ) -> bool:
        for z in zones:
            if allowed_types and str(z.get("type", "")) not in allowed_types:
                continue
            idx = int(z.get("index", 0))
            if idx < min_index:
                continue
            lo = float(z.get("low", 0.0))
            hi = float(z.get("high", 0.0))
            low, high = (lo, hi) if lo <= hi else (hi, lo)
            if low <= price <= high:
                return True
        return False

    @staticmethod
    def _chart_pattern_bias(candles: list[Candle]) -> int:
        # Lightweight chart-pattern approximation for strategy scoring.
        if len(candles) < 24:
            return 0

        highs = [c.high for c in candles[-20:]]
        lows = [c.low for c in candles[-20:]]
        closes = [c.close for c in candles[-20:]]
        last = closes[-1]

        left_high = max(highs[:10])
        right_high = max(highs[10:])
        left_low = min(lows[:10])
        right_low = min(lows[10:])

        # Ascending/descending triangle proxy.
        flat_high = abs(left_high - right_high) / max(last, 1e-9) <= 0.004
        flat_low = abs(left_low - right_low) / max(last, 1e-9) <= 0.004
        rising_lows = right_low > left_low
        falling_highs = right_high < left_high

        if flat_high and rising_lows and last >= right_high * 0.998:
            return 1
        if flat_low and falling_highs and last <= right_low * 1.002:
            return -1

        # Double-bottom / double-top proxy.
        if flat_low and last > (left_high + right_high) / 2:
            return 1
        if flat_high and last < (left_low + right_low) / 2:
            return -1

        return 0

    @staticmethod
    def _near_level(price: float, levels: list[float], threshold: float = 0.0035) -> bool:
        if not levels:
            return False
        return min(abs(price - lv) / max(price, 1e-9) for lv in levels) <= threshold

    @staticmethod
    def _wick_profile(candle: Candle) -> tuple[float, float]:
        rng = max(candle.high - candle.low, 1e-9)
        upper_wick = max(0.0, candle.high - max(candle.open, candle.close))
        lower_wick = max(0.0, min(candle.open, candle.close) - candle.low)
        return upper_wick / rng, lower_wick / rng

    @staticmethod
    def _regime_score(
        ema20: float,
        ema50: float,
        atr: float,
        hist: float,
        rsi: float,
        bos: str,
        choch: str,
    ) -> float:
        ema_gap = abs(ema20 - ema50) / max(atr, 1e-9)
        score = 0.0
        if ema_gap >= 1.3:
            score += 1.25
        elif ema_gap >= 0.9:
            score += 0.9
        elif ema_gap <= 0.35:
            score -= 0.8

        if abs(hist) >= 0.08:
            score += 0.65
        elif abs(hist) <= 0.02:
            score -= 0.45

        if rsi >= 58 or rsi <= 42:
            score += 0.35
        else:
            score -= 0.2

        if "bos" in bos:
            score += 0.45
        if "choch" in choch:
            score += 0.25
        return score

    def generate_signal(self, candles: list[Candle], rule: StrategyRule) -> str:
        if len(candles) < 60:
            return "flat"

        indicators = compute_indicator_pack(candles)
        smc = detect_market_structure(candles)
        closes = [c.close for c in candles]
        last = closes[-1]
        rsi = indicators["rsi_14"]
        hist = indicators["histogram"]
        atr = max(indicators.get("atr_14", 0.0), 1e-6)
        ema20 = indicators.get("ema_20", 0.0)
        ema50 = indicators.get("ema_50", 0.0)
        volume_ratio = self._volume_ratio(candles, lookback=30)
        body_atr_ratio = self._body_atr_ratio(candles, atr)
        pattern_bias = self._chart_pattern_bias(candles)
        trend = str(smc.get("trend", "neutral"))
        bos = str(smc.get("bos", "none"))
        choch = str(smc.get("choch", "none"))
        premium_zone = smc.get("premium_zone")
        discount_zone = smc.get("discount_zone")
        supports = [float(x) for x in smc.get("support", [])]
        resistances = [float(x) for x in smc.get("resistance", [])]
        fvg_zones = smc.get("fvg_zones", [])
        order_blocks = smc.get("order_blocks", [])
        sweeps = smc.get("liquidity_sweeps", [])
        latest_sweep = str(sweeps[-1].get("type", "")) if sweeps else ""
        upper_wick_ratio, lower_wick_ratio = self._wick_profile(candles[-1])
        regime_score = self._regime_score(ema20, ema50, atr, hist, rsi, bos, choch)
        is_choppy = regime_score <= 0.0 and 44 <= rsi <= 56 and abs(hist) <= 0.03

        lookback_window = self._param_int(rule, "zone_recent_window", 28, min_value=8, max_value=100)
        min_zone_index = max(0, len(candles) - lookback_window)
        in_bullish_fvg = self._in_any_zone(last, fvg_zones, {"bullish_fvg"}, min_zone_index)
        in_bearish_fvg = self._in_any_zone(last, fvg_zones, {"bearish_fvg"}, min_zone_index)
        in_bullish_ob = self._in_any_zone(last, order_blocks, {"bullish_ob"}, min_zone_index)
        in_bearish_ob = self._in_any_zone(last, order_blocks, {"bearish_ob"}, min_zone_index)

        if rule.name == "ema_cross":
            if is_choppy:
                return "flat"
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
            min_regime = self._param_float(rule, "min_regime_score", 0.75, min_value=-1.0, max_value=4.0)
            gap_bps = abs(fast_ema - slow_ema) / max(last, 1e-9) * 10000.0
            if gap_bps < min_gap_bps or regime_score < min_regime:
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
            if regime_score < 0.35:
                return "flat"
            lookback = self._param_int(rule, "breakout_lookback", 20, min_value=10, max_value=120)
            buffer_bps = self._param_float(rule, "breakout_buffer_bps", 0.0, min_value=0.0, max_value=60.0)
            volume_mult = self._param_float(rule, "volume_multiplier", 1.1, min_value=0.5, max_value=5.0)
            if len(candles) < lookback + 1:
                return "flat"
            high_lookback = max(c.high for c in candles[-lookback:])
            low_lookback = min(c.low for c in candles[-lookback:])
            up_trigger = high_lookback * (1 + buffer_bps / 10000.0)
            down_trigger = low_lookback * (1 - buffer_bps / 10000.0)

            if last >= up_trigger and volume_ratio >= volume_mult:
                return "long"
            if last <= down_trigger and volume_ratio >= volume_mult:
                return "short"
            return "flat"

        if rule.name == "smc_liquidity_reversal":
            require_choch = self._param_int(rule, "require_choch", 1, min_value=0, max_value=1) == 1
            rsi_floor_long = self._param_float(rule, "long_rsi_floor", 32.0, min_value=5.0, max_value=65.0)
            rsi_cap_short = self._param_float(rule, "short_rsi_cap", 68.0, min_value=35.0, max_value=95.0)
            min_body_atr = self._param_float(rule, "min_body_atr_ratio", 0.45, min_value=0.0, max_value=4.0)
            min_wick_ratio = self._param_float(rule, "min_rejection_wick_ratio", 0.2, min_value=0.0, max_value=0.9)
            min_regime = self._param_float(rule, "min_regime_score", 0.15, min_value=-1.0, max_value=4.0)
            if regime_score < min_regime:
                return "flat"

            bullish_shift = choch == "bullish_choch" or bos == "bullish_bos"
            bearish_shift = choch == "bearish_choch" or bos == "bearish_bos"
            if require_choch:
                bullish_shift = choch == "bullish_choch"
                bearish_shift = choch == "bearish_choch"

            if (
                latest_sweep == "sell_side_sweep"
                and bullish_shift
                and rsi >= rsi_floor_long
                and hist >= 0
                and body_atr_ratio >= min_body_atr
                and lower_wick_ratio >= min_wick_ratio
                and last >= ema20
            ):
                return "long"
            if (
                latest_sweep == "buy_side_sweep"
                and bearish_shift
                and rsi <= rsi_cap_short
                and hist <= 0
                and body_atr_ratio >= min_body_atr
                and upper_wick_ratio >= min_wick_ratio
                and last <= ema20
            ):
                return "short"
            return "flat"

        if rule.name == "fvg_ob_retest":
            if regime_score < 0.2:
                return "flat"
            require_displacement = self._param_int(rule, "require_displacement", 1, min_value=0, max_value=1) == 1
            min_body_atr = self._param_float(rule, "min_body_atr_ratio", 0.35, min_value=0.0, max_value=4.0)
            max_rsi_long = self._param_float(rule, "max_rsi_long", 67.0, min_value=40.0, max_value=95.0)
            min_rsi_short = self._param_float(rule, "min_rsi_short", 33.0, min_value=5.0, max_value=60.0)
            bullish_retest = in_bullish_fvg or in_bullish_ob
            bearish_retest = in_bearish_fvg or in_bearish_ob
            bullish_displacement = (not require_displacement) or body_atr_ratio >= min_body_atr
            bearish_displacement = (not require_displacement) or body_atr_ratio >= min_body_atr

            if (
                bullish_retest
                and (trend == "uptrend" or bos == "bullish_bos")
                and hist >= 0
                and rsi <= max_rsi_long
                and bullish_displacement
            ):
                return "long"
            if (
                bearish_retest
                and (trend == "downtrend" or bos == "bearish_bos")
                and hist <= 0
                and rsi >= min_rsi_short
                and bearish_displacement
            ):
                return "short"
            return "flat"

        if rule.name == "volume_displacement_breakout":
            lookback = self._param_int(rule, "breakout_lookback", 24, min_value=10, max_value=140)
            volume_mult = self._param_float(rule, "volume_multiplier", 1.35, min_value=0.5, max_value=5.0)
            buffer_bps = self._param_float(rule, "breakout_buffer_bps", 5.0, min_value=0.0, max_value=80.0)
            min_body_atr = self._param_float(rule, "min_body_atr_ratio", 0.65, min_value=0.0, max_value=5.0)
            min_regime = self._param_float(rule, "min_regime_score", 0.9, min_value=-1.0, max_value=4.0)
            if regime_score < min_regime:
                return "flat"
            if len(candles) < lookback + 2:
                return "flat"
            high_ref = max(c.high for c in candles[-(lookback + 1) : -1])
            low_ref = min(c.low for c in candles[-(lookback + 1) : -1])
            up_trigger = high_ref * (1 + buffer_bps / 10000.0)
            down_trigger = low_ref * (1 - buffer_bps / 10000.0)

            bullish_break = (
                last >= up_trigger
                and volume_ratio >= volume_mult
                and body_atr_ratio >= min_body_atr
                and ema20 >= ema50
                and hist >= 0
            )
            bearish_break = (
                last <= down_trigger
                and volume_ratio >= volume_mult
                and body_atr_ratio >= min_body_atr
                and ema20 <= ema50
                and hist <= 0
            )
            if bullish_break:
                return "long"
            if bearish_break:
                return "short"
            return "flat"

        if rule.name == "premium_discount_reversion":
            long_rsi_max = self._param_float(rule, "long_rsi_max", 45.0, min_value=10.0, max_value=65.0)
            short_rsi_min = self._param_float(rule, "short_rsi_min", 55.0, min_value=35.0, max_value=95.0)
            near_level_threshold = self._param_float(rule, "level_threshold", 0.0035, min_value=0.001, max_value=0.03)
            max_regime = self._param_float(rule, "max_regime_score", 1.2, min_value=-1.0, max_value=5.0)
            if regime_score > max_regime:
                return "flat"

            in_discount = self._in_price_zone(last, discount_zone)
            in_premium = self._in_price_zone(last, premium_zone)
            near_support = self._near_level(last, supports, threshold=near_level_threshold)
            near_resistance = self._near_level(last, resistances, threshold=near_level_threshold)

            if (
                in_discount
                and (trend == "uptrend" or choch == "bullish_choch" or bos == "bullish_bos")
                and (latest_sweep == "sell_side_sweep" or near_support)
                and rsi <= long_rsi_max
                and hist >= -0.02
            ):
                return "long"
            if (
                in_premium
                and (trend == "downtrend" or choch == "bearish_choch" or bos == "bearish_bos")
                and (latest_sweep == "buy_side_sweep" or near_resistance)
                and rsi >= short_rsi_min
                and hist <= 0.02
            ):
                return "short"
            return "flat"

        if rule.name == "hybrid_confluence_intraday":
            news_score = self._param_float(rule, "news_score", 0.5, min_value=0.0, max_value=1.0)
            fundamental_score = self._param_float(rule, "fundamental_score", 0.5, min_value=0.0, max_value=1.0)
            long_threshold = self._param_float(rule, "long_threshold", 3.4, min_value=1.0, max_value=10.0)
            short_threshold = self._param_float(rule, "short_threshold", 3.4, min_value=1.0, max_value=10.0)
            min_regime = self._param_float(rule, "min_regime_score", 0.4, min_value=-1.0, max_value=5.0)
            if regime_score < min_regime:
                return "flat"

            long_score = 0.0
            short_score = 0.0

            if ema20 > ema50:
                long_score += 1.0
            elif ema20 < ema50:
                short_score += 1.0

            if hist > 0:
                long_score += 0.8
            elif hist < 0:
                short_score += 0.8

            if bos == "bullish_bos":
                long_score += 1.2
            elif bos == "bearish_bos":
                short_score += 1.2

            if choch == "bullish_choch":
                long_score += 0.8
            elif choch == "bearish_choch":
                short_score += 0.8

            if pattern_bias > 0:
                long_score += 0.9
            elif pattern_bias < 0:
                short_score += 0.9

            if volume_ratio >= 1.2 and body_atr_ratio >= 0.55:
                if last >= ema20:
                    long_score += 0.5
                if last <= ema20:
                    short_score += 0.5

            if self._in_price_zone(last, discount_zone):
                long_score += 0.45
            if self._in_price_zone(last, premium_zone):
                short_score += 0.45

            long_score += max(0.0, (news_score - 0.5) * 3.0)
            short_score += max(0.0, (0.5 - news_score) * 3.0)
            long_score += max(0.0, (fundamental_score - 0.5) * 2.5)
            short_score += max(0.0, (0.5 - fundamental_score) * 2.5)
            if regime_score >= 1.5:
                if ema20 > ema50:
                    long_score += 0.35
                elif ema20 < ema50:
                    short_score += 0.35

            if long_score >= long_threshold and long_score > short_score + 0.35:
                return "long"
            if short_score >= short_threshold and short_score > long_score + 0.35:
                return "short"
            return "flat"

        if rule.name == "trend_pullback_confluence":
            if regime_score < 0.8:
                return "flat"
            pullback_atr = self._param_float(rule, "pullback_atr", 1.0, min_value=0.1, max_value=3.0)
            min_volume_ratio = self._param_float(rule, "min_volume_ratio", 0.8, min_value=0.3, max_value=4.0)
            max_rsi_long = self._param_float(rule, "max_rsi_long", 68.0, min_value=40.0, max_value=95.0)
            min_rsi_short = self._param_float(rule, "min_rsi_short", 32.0, min_value=5.0, max_value=60.0)
            proximity_ema20 = abs(last - ema20) / max(atr, 1e-9)

            if (
                trend == "uptrend"
                and ema20 >= ema50
                and proximity_ema20 <= pullback_atr
                and hist >= 0
                and rsi <= max_rsi_long
                and (bos == "bullish_bos" or choch == "bullish_choch")
                and volume_ratio >= min_volume_ratio
            ):
                return "long"
            if (
                trend == "downtrend"
                and ema20 <= ema50
                and proximity_ema20 <= pullback_atr
                and hist <= 0
                and rsi >= min_rsi_short
                and (bos == "bearish_bos" or choch == "bearish_choch")
                and volume_ratio >= min_volume_ratio
            ):
                return "short"
            return "flat"

        if rule.name == "regime_adaptive_breakout":
            lookback = self._param_int(rule, "breakout_lookback", 22, min_value=10, max_value=160)
            buffer_bps = self._param_float(rule, "breakout_buffer_bps", 5.0, min_value=0.0, max_value=120.0)
            volume_mult = self._param_float(rule, "volume_multiplier", 1.2, min_value=0.4, max_value=5.0)
            trend_regime_threshold = self._param_float(rule, "trend_regime_threshold", 0.9, min_value=-1.0, max_value=5.0)
            if len(candles) < lookback + 2:
                return "flat"

            high_ref = max(c.high for c in candles[-(lookback + 1) : -1])
            low_ref = min(c.low for c in candles[-(lookback + 1) : -1])
            up_trigger = high_ref * (1 + buffer_bps / 10000.0)
            down_trigger = low_ref * (1 - buffer_bps / 10000.0)

            if regime_score >= trend_regime_threshold:
                if (
                    last >= up_trigger
                    and volume_ratio >= volume_mult
                    and ema20 >= ema50
                    and hist >= 0
                ):
                    return "long"
                if (
                    last <= down_trigger
                    and volume_ratio >= volume_mult
                    and ema20 <= ema50
                    and hist <= 0
                ):
                    return "short"
                return "flat"

            # Range/chop regime: revert from premium/discount zones with structure hint.
            in_discount = self._in_price_zone(last, discount_zone)
            in_premium = self._in_price_zone(last, premium_zone)
            if in_discount and (latest_sweep == "sell_side_sweep" or choch == "bullish_choch") and rsi <= 47:
                return "long"
            if in_premium and (latest_sweep == "buy_side_sweep" or choch == "bearish_choch") and rsi >= 53:
                return "short"
            return "flat"

        if rule.name == "liquidity_trap_reversal":
            min_wick_ratio = self._param_float(rule, "min_wick_ratio", 0.32, min_value=0.1, max_value=0.95)
            min_body_atr = self._param_float(rule, "min_body_atr_ratio", 0.2, min_value=0.0, max_value=3.0)
            if body_atr_ratio < min_body_atr:
                return "flat"

            if (
                latest_sweep == "sell_side_sweep"
                and lower_wick_ratio >= min_wick_ratio
                and (choch == "bullish_choch" or bos == "bullish_bos")
                and hist >= -0.01
                and last >= ema20
            ):
                return "long"
            if (
                latest_sweep == "buy_side_sweep"
                and upper_wick_ratio >= min_wick_ratio
                and (choch == "bearish_choch" or bos == "bearish_bos")
                and hist <= 0.01
                and last <= ema20
            ):
                return "short"
            return "flat"

        # smc_breakout
        if is_choppy:
            return "flat"
        bull_rsi_min = self._param_float(rule, "bull_rsi_min", 48.0, min_value=20.0, max_value=80.0)
        bear_rsi_max = self._param_float(rule, "bear_rsi_max", 52.0, min_value=20.0, max_value=80.0)
        require_displacement = (
            self._param_int(rule, "require_displacement", 1, min_value=0, max_value=1) == 1
        )
        min_hist = self._param_float(rule, "min_histogram_strength", 0.01, min_value=0.0, max_value=10.0)
        min_volume_ratio = self._param_float(rule, "min_volume_ratio", 0.95, min_value=0.3, max_value=5.0)
        min_regime = self._param_float(rule, "min_regime_score", 0.55, min_value=-1.0, max_value=5.0)
        if regime_score < min_regime:
            return "flat"

        bullish_displacement = not require_displacement or hist >= min_hist
        bearish_displacement = not require_displacement or hist <= -min_hist

        if (
            smc["bos"] == "bullish_bos"
            and smc["trend"] == "uptrend"
            and rsi >= bull_rsi_min
            and bullish_displacement
            and volume_ratio >= min_volume_ratio
        ):
            return "long"
        if (
            smc["bos"] == "bearish_bos"
            and smc["trend"] == "downtrend"
            and rsi <= bear_rsi_max
            and bearish_displacement
            and volume_ratio >= min_volume_ratio
        ):
            return "short"
        return "flat"
