from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.trading import OrderRequest, OrderResponse
from app.models.workflow import AutoPaperWorkflowRequest, AutoPaperWorkflowResponse
from app.services.auto_workflow import AutoPaperWorkflowService
from app.services.groww_client import GrowwBrokerClient
from app.services.market_data import DataProvider
from app.services.notification_service import NotificationService
from app.services.risk import pre_trade_checks

router = APIRouter()
broker = GrowwBrokerClient()
notifier = NotificationService()
data = DataProvider()
auto_workflow = AutoPaperWorkflowService()


@router.post("/trading/order", response_model=OrderResponse)
async def place_order(req: OrderRequest) -> OrderResponse:
    settings = get_settings()
    if req.order_type == "limit" and req.limit_price:
        order_price = req.limit_price
    else:
        order_price = data.get_candles(req.symbol, "1m", 1)[-1].close
    notional = float(req.qty) * float(order_price)

    ok, msg = pre_trade_checks(
        notional=notional,
        mode=req.mode,
        max_order_notional=settings.max_order_notional,
        live_enabled=settings.live_trading_enabled,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    try:
        payload = await broker.place_order(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Broker order failed: {exc}") from exc

    notifier.send_whatsapp(
        f"Order {payload['status']}: {req.symbol} {req.side.upper()} qty={req.qty} mode={req.mode}"
    )

    return OrderResponse(**payload)


@router.post("/notifications/whatsapp/test")
def whatsapp_test(message: str = "Trading system alert channel is active") -> dict:
    return notifier.send_whatsapp(message)


@router.post("/trading/workflow/auto-paper", response_model=AutoPaperWorkflowResponse)
async def run_auto_paper_workflow(req: AutoPaperWorkflowRequest) -> AutoPaperWorkflowResponse:
    return await auto_workflow.run(req)
