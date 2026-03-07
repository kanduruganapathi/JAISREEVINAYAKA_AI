from typing import Literal

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    symbol: str
    segment: Literal["equity", "index_option", "stock_option"]
    side: Literal["buy", "sell"]
    qty: int = Field(gt=0)
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = None
    product_type: Literal["intraday", "delivery"] = "intraday"
    mode: Literal["paper", "live"] = "paper"


class OrderResponse(BaseModel):
    order_id: str
    status: Literal["accepted", "rejected", "simulated"]
    mode: str
    message: str
    broker_payload: dict = Field(default_factory=dict)
