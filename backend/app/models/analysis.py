from typing import Any, Literal

from pydantic import BaseModel, Field


class Candle(BaseModel):
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class AnalysisRequest(BaseModel):
    symbol: str = Field(..., description="Ticker or instrument symbol")
    segment: Literal[
        "equity",
        "index",
        "intraday_options",
        "stock_options",
        "swing_stock",
    ] = "equity"
    primary_timeframe: str = "15m"
    secondary_timeframes: list[str] = Field(default_factory=lambda: ["5m", "1h", "1d"])
    candles: list[Candle] = Field(default_factory=list)
    include_fundamental: bool = True
    include_technical: bool = True
    include_news: bool = True
    include_events: bool = True
    include_smc: bool = True
    include_price_action: bool = True
    include_indicators: bool = True
    mode: Literal["advisory", "autonomous"] = "advisory"


class AgentSignal(BaseModel):
    agent: str
    bias: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskSnapshot(BaseModel):
    max_position_size: float
    stop_loss_pct: float
    take_profit_pct: float
    risk_reward_ratio: float
    warnings: list[str] = Field(default_factory=list)


class TradePlan(BaseModel):
    action: Literal["buy", "sell", "hold"]
    entry: float | None = None
    stop_loss: float | None = None
    target: float | None = None
    rationale: str


class TimeframeBias(BaseModel):
    timeframe: str
    bias: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    note: str


class StrategyIdea(BaseModel):
    name: str
    instrument: str
    direction: Literal["bullish", "bearish", "neutral"]
    setup: str
    entry_trigger: str
    stop_rule: str
    targets: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    timeframe: str


class MarketStructureSnapshot(BaseModel):
    trend: str
    bos: str
    choch: str
    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)
    premium_zone: dict[str, float] | None = None
    discount_zone: dict[str, float] | None = None
    liquidity_sweeps: list[dict[str, Any]] = Field(default_factory=list)
    fvg_zones: list[dict[str, Any]] = Field(default_factory=list)
    order_blocks: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    symbol: str
    segment: str
    regime: str
    score: float
    consensus_bias: str
    trade_plan: TradePlan
    risk: RiskSnapshot
    indicator_snapshot: dict[str, float] = Field(default_factory=dict)
    timeframe_biases: list[TimeframeBias] = Field(default_factory=list)
    market_structure: MarketStructureSnapshot | None = None
    strategy_ideas: list[StrategyIdea] = Field(default_factory=list)
    execution_checklist: list[str] = Field(default_factory=list)
    signals: list[AgentSignal]
    timestamp: str
