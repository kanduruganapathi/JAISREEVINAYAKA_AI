from typing import Literal

from pydantic import BaseModel, Field


class AutoPaperWorkflowRequest(BaseModel):
    universe: Literal["nifty50", "custom"] = "nifty50"
    symbols: list[str] = Field(default_factory=list)
    timeframe: str = "15m"
    top_n: int = Field(default=12, ge=1, le=50)
    include_news: bool = True
    include_fundamental: bool = True
    include_breakout: bool = True
    include_technical: bool = True
    backtest_lookback_candles: int = Field(default=380, ge=120, le=2000)
    initial_capital: float = Field(default=100000.0, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, ge=0.1, le=5.0)
    max_paper_trades: int = Field(default=3, ge=1, le=20)
    min_scanner_score: float = Field(default=0.58, ge=0.0, le=1.0)
    min_backtest_win_rate: float = Field(default=45.0, ge=0.0, le=100.0)
    min_backtest_return_pct: float = Field(default=0.0, ge=-100.0, le=10000.0)
    min_backtest_sharpe: float = Field(default=0.0, ge=-10.0, le=100.0)
    min_backtest_trades: int = Field(default=4, ge=1, le=1000)
    require_directional_action: bool = True


class AutoBacktestSummary(BaseModel):
    total_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    sharpe: float
    trades: int


class AutoGateResult(BaseModel):
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class AutoRiskPlan(BaseModel):
    side: Literal["buy", "sell"]
    qty: int
    entry_price: float
    stop_distance: float
    notional: float


class AutoOrderResult(BaseModel):
    order_id: str
    status: str
    mode: str
    message: str


class AutoPaperWorkflowItem(BaseModel):
    symbol: str
    rank: int
    scanner_score: float
    scanner_bias: Literal["bullish", "bearish", "neutral"]
    scanner_action: Literal["buy", "sell", "watch"]
    chosen_strategy: str
    strategy_params: dict[str, float] = Field(default_factory=dict)
    backtest: AutoBacktestSummary
    gate: AutoGateResult
    risk_plan: AutoRiskPlan | None = None
    order: AutoOrderResult | None = None


class AutoWorkflowSummary(BaseModel):
    scanned: int
    selected_for_backtest: int
    qualified_for_paper: int
    paper_orders: int
    rejected: int


class AutoPaperWorkflowResponse(BaseModel):
    generated_at: str
    timeframe: str
    universe: str
    summary: AutoWorkflowSummary
    results: list[AutoPaperWorkflowItem] = Field(default_factory=list)
