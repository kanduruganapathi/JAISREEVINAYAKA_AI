from fastapi import APIRouter

from app.models.strategy import BacktestRequest, BacktestResponse
from app.services.backtest import BacktestService
from app.services.market_data import DataProvider

router = APIRouter()
service = BacktestService()
data = DataProvider()


@router.post("/backtest/run", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest) -> BacktestResponse:
    if not req.candles:
        timeframe = req.timeframe or "15m"
        lookback = max(120, min(req.lookback_candles, 2000))
        req.candles = data.get_candles(req.symbol, timeframe, lookback)
    return service.run(req)
