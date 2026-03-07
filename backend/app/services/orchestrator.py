from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.events import EventAgent
from app.agents.fundamental import FundamentalAgent
from app.agents.news import NewsAgent
from app.agents.risk import RiskAgent
from app.agents.smc import SMCPriceActionAgent
from app.agents.synthesis import SynthesisAgent
from app.agents.technical import TechnicalAgent
from app.models.analysis import AnalysisRequest, AnalysisResponse
from app.services.indicators import compute_indicator_pack
from app.services.market_data import DataProvider
from app.services.risk import build_risk_snapshot


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self.data = DataProvider()
        self.synthesis = SynthesisAgent()
        self.fundamental = FundamentalAgent()
        self.technical = TechnicalAgent()
        self.news = NewsAgent()
        self.events = EventAgent()
        self.smc = SMCPriceActionAgent()
        self.risk_agent = RiskAgent()

    async def run(self, req: AnalysisRequest, capital: float = 100000.0) -> AnalysisResponse:
        timeframes = [req.primary_timeframe] + [t for t in req.secondary_timeframes if t != req.primary_timeframe]
        candles_by_tf = {}

        for tf in timeframes:
            candles_by_tf[tf] = req.candles if req.candles and tf == req.primary_timeframe else self.data.get_candles(req.symbol, tf)

        selected_agents = []
        if req.include_fundamental and req.segment not in {"intraday_options", "stock_options"}:
            selected_agents.append(self.fundamental)
        if req.include_technical:
            selected_agents.append(self.technical)
        if req.include_news:
            selected_agents.append(self.news)
        if req.include_events:
            selected_agents.append(self.events)
        if req.include_smc or req.include_price_action:
            selected_agents.append(self.smc)
        selected_agents.append(self.risk_agent)

        signals = await asyncio.gather(*[agent.run(req, candles_by_tf) for agent in selected_agents])

        primary = candles_by_tf[req.primary_timeframe]
        last_price = primary[-1].close
        ind = compute_indicator_pack(primary)
        avg_conf = sum(s.confidence for s in signals) / len(signals)

        risk = build_risk_snapshot(
            capital=capital,
            price=last_price,
            volatility=ind.get("volatility", 0.2),
            confidence=avg_conf,
            segment=req.segment,
        )

        consensus, score, plan, regime = self.synthesis.synthesize(signals, last_price, risk)

        return AnalysisResponse(
            symbol=req.symbol,
            segment=req.segment,
            regime=regime,
            score=score,
            consensus_bias=consensus,
            trade_plan=plan,
            risk=risk,
            signals=signals,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
