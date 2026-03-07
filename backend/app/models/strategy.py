from typing import Literal

from pydantic import BaseModel, Field

from app.models.analysis import Candle


class StrategyRule(BaseModel):
    name: Literal[
        "smc_breakout",
        "ema_cross",
        "rsi_reversion",
        "multi_timeframe_breakout",
    ]
    params: dict[str, float | int | str] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    symbol: str
    segment: str = "equity"
    candles: list[Candle]
    timeframe: str = "15m"
    lookback_candles: int = Field(default=380, ge=120, le=2000)
    initial_capital: float = 100000.0
    commission_per_trade: float = 20.0
    slippage_bps: float = 5.0
    rule: StrategyRule


class EquityPoint(BaseModel):
    ts: str
    equity: float


class TradeRecord(BaseModel):
    entry_ts: str
    exit_ts: str
    side: Literal["long", "short"]
    entry: float
    exit: float
    qty: float
    pnl: float
    pnl_pct: float


class BacktestResponse(BaseModel):
    symbol: str
    total_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: list[TradeRecord]
    equity_curve: list[EquityPoint]
