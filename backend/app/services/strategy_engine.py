from __future__ import annotations

from app.models.analysis import Candle
from app.models.strategy import StrategyRule
from app.services.indicators import compute_indicator_pack
from app.services.smc import detect_market_structure


class StrategyEngine:
    def generate_signal(self, candles: list[Candle], rule: StrategyRule) -> str:
        if len(candles) < 60:
            return "flat"

        indicators = compute_indicator_pack(candles)
        smc = detect_market_structure(candles)
        last = candles[-1].close

        if rule.name == "ema_cross":
            if indicators["ema_20"] > indicators["ema_50"] and last > indicators["ema_20"]:
                return "long"
            if indicators["ema_20"] < indicators["ema_50"] and last < indicators["ema_20"]:
                return "short"
            return "flat"

        if rule.name == "rsi_reversion":
            if indicators["rsi_14"] < 30:
                return "long"
            if indicators["rsi_14"] > 70:
                return "short"
            return "flat"

        if rule.name == "multi_timeframe_breakout":
            high_20 = max(c.high for c in candles[-20:])
            low_20 = min(c.low for c in candles[-20:])
            if last >= high_20:
                return "long"
            if last <= low_20:
                return "short"
            return "flat"

        # smc_breakout
        if smc["bos"] == "bullish_bos" and smc["trend"] == "uptrend":
            return "long"
        if smc["bos"] == "bearish_bos" and smc["trend"] == "downtrend":
            return "short"
        return "flat"
