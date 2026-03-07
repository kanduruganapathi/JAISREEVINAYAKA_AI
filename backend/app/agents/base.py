from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.analysis import AgentSignal, AnalysisRequest


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def run(self, request: AnalysisRequest, candles_by_tf: dict[str, list]) -> AgentSignal:
        raise NotImplementedError
