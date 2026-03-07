from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest
from app.services.indicators import compute_indicator_pack


class TechnicalAgent(BaseAgent):
    name = "technical_analyst"

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        candles = candles_by_tf[request.primary_timeframe]
        indicators = compute_indicator_pack(candles)

        bullish = 0
        bearish = 0

        if indicators["ema_20"] > indicators["ema_50"]:
            bullish += 1
        else:
            bearish += 1

        if indicators["histogram"] > 0:
            bullish += 1
        else:
            bearish += 1

        if indicators["rsi_14"] > 70:
            bearish += 1
        elif indicators["rsi_14"] < 30:
            bullish += 1

        if bullish > bearish:
            bias = "bullish"
            confidence = 0.5 + min(0.4, bullish * 0.12)
        elif bearish > bullish:
            bias = "bearish"
            confidence = 0.5 + min(0.4, bearish * 0.12)
        else:
            bias = "neutral"
            confidence = 0.5

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=round(confidence, 2),
            summary="Technical confluence from EMA trend, RSI, MACD, volatility.",
            details=indicators,
        )
