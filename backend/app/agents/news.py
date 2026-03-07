from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.analysis import AgentSignal, AnalysisRequest
from app.services.news_service import NewsService


class NewsAgent(BaseAgent):
    name = "news_analyst"

    def __init__(self) -> None:
        self.news = NewsService()

    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        summary = self.news.summarize(request.symbol)
        sentiment = summary["sentiment"]
        score = summary["score"]

        if sentiment == "positive":
            bias = "bullish"
        elif sentiment == "negative":
            bias = "bearish"
        else:
            bias = "neutral"

        return AgentSignal(
            agent=self.name,
            bias=bias,
            confidence=score,
            summary="News sentiment and headline risk scan.",
            details=summary,
        )
