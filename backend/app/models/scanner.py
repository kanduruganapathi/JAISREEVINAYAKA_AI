from typing import Literal

from pydantic import BaseModel, Field


class StockScanRequest(BaseModel):
    universe: Literal["nifty50", "custom"] = "nifty50"
    symbols: list[str] = Field(default_factory=list)
    timeframe: str = "15m"
    top_n: int = 12
    include_news: bool = True
    include_fundamental: bool = True
    include_breakout: bool = True
    include_technical: bool = True


class ScanFactor(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    signal: Literal["bullish", "bearish", "neutral"]
    summary: str
    meta: dict[str, str] = Field(default_factory=dict)


class IntradayPlan(BaseModel):
    direction: Literal["long", "short", "neutral"]
    setup: str
    entry_zone: str
    stop_loss: str
    targets: list[str] = Field(default_factory=list)
    invalidation: str
    rr_estimate: float = 0.0


class MarketSnapshot(BaseModel):
    live_price: float = 0.0
    open_price: float = 0.0
    close_price: float = 0.0
    prev_close: float = 0.0
    day_high: float = 0.0
    day_low: float = 0.0
    change_pct: float = 0.0
    volume: float = 0.0


class StrategyValidation(BaseModel):
    strategy: str
    total_return_pct: float = 0.0
    win_rate_pct: float = 0.0
    sharpe: float = 0.0
    trades: int = 0
    status: Literal["pass", "watch", "fail"] = "watch"
    reason: str = ""


class StockScanResult(BaseModel):
    symbol: str
    rank: int
    overall_score: float = Field(ge=0.0, le=1.0)
    bias: Literal["bullish", "bearish", "neutral"]
    action: Literal["buy", "sell", "watch"]
    technical: ScanFactor
    breakout: ScanFactor
    fundamental: ScanFactor
    news: ScanFactor
    technical_snapshot: dict[str, float] = Field(default_factory=dict)
    market_snapshot: MarketSnapshot = Field(default_factory=MarketSnapshot)
    strategy_validation: StrategyValidation | None = None
    intraday_plan: IntradayPlan


class StockScanSummary(BaseModel):
    scanned: int
    bullish: int
    bearish: int
    neutral: int
    high_confidence: int


class StockScanResponse(BaseModel):
    universe: str
    timeframe: str
    generated_at: str
    summary: StockScanSummary
    results: list[StockScanResult]
