from __future__ import annotations

import asyncio

from app.models.analysis import AnalysisRequest
from app.models.portfolio import PortfolioRequest, Position
from app.models.strategy import BacktestRequest, StrategyRule
from app.models.trading import OrderRequest
from app.services.backtest import BacktestService
from app.services.orchestrator import MultiAgentOrchestrator
from app.services.portfolio_service import PortfolioService
from app.services.groww_client import GrowwBrokerClient


orchestrator = MultiAgentOrchestrator()
backtest_service = BacktestService()
portfolio_service = PortfolioService()
broker = GrowwBrokerClient()


def analyze_symbol(symbol: str, segment: str = "equity", timeframe: str = "15m") -> dict:
    req = AnalysisRequest(symbol=symbol, segment=segment, primary_timeframe=timeframe)
    result = asyncio.run(orchestrator.run(req))
    return result.model_dump()


def backtest_symbol(symbol: str, strategy: str = "smc_breakout") -> dict:
    candles = orchestrator.data.get_candles(symbol, "15m", 350)
    req = BacktestRequest(
        symbol=symbol,
        segment="equity",
        candles=candles,
        rule=StrategyRule(name=strategy, params={}),
    )
    result = backtest_service.run(req)
    return result.model_dump()


def portfolio_snapshot(capital: float, holdings: list[dict]) -> dict:
    positions = [Position(**item) for item in holdings]
    req = PortfolioRequest(capital=capital, positions=positions)
    result = portfolio_service.analyze(req)
    return result.model_dump()


def place_paper_order(symbol: str, side: str, qty: int, segment: str = "equity") -> dict:
    req = OrderRequest(
        symbol=symbol,
        segment="equity" if segment == "equity" else "stock_option",
        side=side,
        qty=qty,
        order_type="market",
        product_type="intraday",
        mode="paper",
    )
    result = asyncio.run(broker.place_order(req))
    return result
