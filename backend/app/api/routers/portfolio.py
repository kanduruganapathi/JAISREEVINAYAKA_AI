from fastapi import APIRouter

from app.models.portfolio import PortfolioRequest, PortfolioResponse
from app.services.portfolio_service import PortfolioService

router = APIRouter()
service = PortfolioService()


@router.post("/portfolio/analyze", response_model=PortfolioResponse)
def analyze_portfolio(req: PortfolioRequest) -> PortfolioResponse:
    return service.analyze(req)
