from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest
from app.services.smc import detect_market_structure


class SMCPriceActionAgent(BaseAgent):
    name = "smc_price_action_analyst"

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        candles = candles_by_tf[request.primary_timeframe]
        smc = detect_market_structure(candles)

        bullish = 0
        bearish = 0

        if smc["bos"] == "bullish_bos":
            bullish += 1
        elif smc["bos"] == "bearish_bos":
            bearish += 1

        if smc["choch"] == "bullish_choch":
            bullish += 1
        elif smc["choch"] == "bearish_choch":
            bearish += 1

        if smc["trend"] == "uptrend":
            bullish += 1
        elif smc["trend"] == "downtrend":
            bearish += 1

        if bullish > bearish:
            bias = "bullish"
            confidence = 0.56 + min(0.35, bullish * 0.1)
        elif bearish > bullish:
            bias = "bearish"
            confidence = 0.56 + min(0.35, bearish * 0.1)
        else:
            bias = "neutral"
            confidence = 0.5

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=round(confidence, 2),
            summary="SMC + price action: BOS/CHOCH/FVG/OB/liquidity/support-resistance context.",
            details=smc,
        )
