from pydantic import BaseModel, Field


class Position(BaseModel):
    symbol: str
    qty: float
    avg_price: float
    last_price: float


class PortfolioRequest(BaseModel):
    capital: float
    positions: list[Position] = Field(default_factory=list)


class PositionMetrics(BaseModel):
    symbol: str
    market_value: float
    invested_value: float
    pnl: float
    pnl_pct: float
    weight_pct: float


class PortfolioResponse(BaseModel):
    total_value: float
    invested_value: float
    total_pnl: float
    total_pnl_pct: float
    concentration_risk_pct: float
    value_at_risk_95: float
    recommendations: list[str]
    positions: list[PositionMetrics]


class GrowwSyncMeta(BaseModel):
    status: str
    source: str
    message: str
    total_positions: int


class GrowwPortfolioSyncResponse(BaseModel):
    sync: GrowwSyncMeta
    positions: list[Position]
    analysis: PortfolioResponse
