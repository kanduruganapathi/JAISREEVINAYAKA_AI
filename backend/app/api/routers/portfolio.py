from fastapi import APIRouter

from app.models.portfolio import (
    GrowwPortfolioSyncResponse,
    GrowwSyncMeta,
    PortfolioRequest,
    PortfolioResponse,
    Position,
)
from app.services.groww_client import GrowwBrokerClient
from app.services.portfolio_service import PortfolioService

router = APIRouter()
service = PortfolioService()
broker = GrowwBrokerClient()


@router.post("/portfolio/analyze", response_model=PortfolioResponse)
def analyze_portfolio(req: PortfolioRequest) -> PortfolioResponse:
    return service.analyze(req)


@router.post("/portfolio/groww/sync", response_model=GrowwPortfolioSyncResponse)
async def sync_groww_portfolio() -> GrowwPortfolioSyncResponse:
    synced = await broker.fetch_portfolio()
    positions = [Position(**item) for item in synced["positions"]]
    capital = sum(p.qty * p.last_price for p in positions)
    analysis = service.analyze(PortfolioRequest(capital=capital, positions=positions))
    return GrowwPortfolioSyncResponse(
        sync=GrowwSyncMeta(
            status=synced["status"],
            source=synced["source"],
            message=synced["message"],
            total_positions=len(positions),
        ),
        positions=positions,
        analysis=analysis,
    )
