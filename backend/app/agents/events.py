from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest
from app.services.event_service import EventService


class EventAgent(BaseAgent):
    name = "event_analyst"

    def __init__(self) -> None:
        self.events = EventService()

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        payload = self.events.upcoming(request.symbol)
        high_impact = sum(1 for e in payload["events"] if e["impact"] == "high")

        if high_impact >= 1:
            bias = "neutral"
            confidence = 0.58
            summary = "High-impact events ahead. Use reduced risk and time filters."
        else:
            bias = "neutral"
            confidence = 0.5
            summary = "No dominant event risk currently."

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=confidence,
            summary=summary,
            details=payload,
        )
