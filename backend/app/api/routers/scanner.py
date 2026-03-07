from fastapi import APIRouter

from app.models.scanner import StockScanRequest, StockScanResponse
from app.services.scanner import StockScannerService

router = APIRouter()
service = StockScannerService()


@router.post('/scanner/run', response_model=StockScanResponse)
def run_scanner(req: StockScanRequest) -> StockScanResponse:
    return service.run(req)
