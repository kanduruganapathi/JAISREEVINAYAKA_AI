from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest
from app.services.indicators import compute_indicator_pack


class RiskAgent(BaseAgent):
    name = "risk_analyst"

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        candles = candles_by_tf[request.primary_timeframe]
        ind = compute_indicator_pack(candles)
        vol = ind.get("volatility", 0.0)

        if vol > 0.4:
            bias = "bearish"
            confidence = 0.72
            summary = "Elevated volatility risk; reduce leverage and trade frequency."
        elif vol < 0.18:
            bias = "bullish"
            confidence = 0.62
            summary = "Controlled volatility supports systematic execution."
        else:
            bias = "neutral"
            confidence = 0.55
            summary = "Balanced volatility regime."

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=confidence,
            summary=summary,
            details={"volatility": vol, "atr_14": ind.get("atr_14", 0.0)},
        )
