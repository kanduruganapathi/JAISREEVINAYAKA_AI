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
        req.candles = data.get_candles(req.symbol, "15m", 380)
    return service.run(req)
