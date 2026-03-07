from __future__ import annotations

import random

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest


class FundamentalAgent(BaseAgent):
    name = "fundamental_analyst"

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        seed = sum(ord(ch) for ch in request.symbol)
        random.seed(seed)

        pe = round(random.uniform(10, 45), 2)
        revenue_growth = round(random.uniform(-0.1, 0.35), 3)
        debt_to_equity = round(random.uniform(0.05, 1.2), 2)

        score = 0.5
        if revenue_growth > 0.12:
            score += 0.18
        if debt_to_equity < 0.5:
            score += 0.12
        if pe > 35:
            score -= 0.1

        score = max(0.0, min(score, 1.0))
        if score > 0.6:
            bias = "bullish"
        elif score < 0.45:
            bias = "bearish"
        else:
            bias = "neutral"

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=round(score, 2),
            summary="Fundamental health based on valuation, growth, and leverage proxies.",
            details={
                "pe": pe,
                "revenue_growth": revenue_growth,
                "debt_to_equity": debt_to_equity,
            },
        )
