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


class IntradayPlan(BaseModel):
    direction: Literal["long", "short", "neutral"]
    setup: str
    entry_zone: str
    stop_loss: str
    targets: list[str] = Field(default_factory=list)
    invalidation: str
    rr_estimate: float = 0.0


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
