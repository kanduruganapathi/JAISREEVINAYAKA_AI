from fastapi import APIRouter, Query

from app.models.analysis import AnalysisRequest, AnalysisResponse
from app.services.notification_service import NotificationService
from app.services.orchestrator import MultiAgentOrchestrator

router = APIRouter()
orchestrator = MultiAgentOrchestrator()
notifier = NotificationService()


@router.post("/analysis/run", response_model=AnalysisResponse)
async def run_analysis(req: AnalysisRequest, notify: bool = Query(default=False)) -> AnalysisResponse:
    result = await orchestrator.run(req)
    if notify and result.trade_plan.action != "hold":
        notifier.send_whatsapp(
            (
                f"{result.symbol} {result.segment} alert: {result.trade_plan.action.upper()} "
                f"entry={result.trade_plan.entry} stop={result.trade_plan.stop_loss} "
                f"target={result.trade_plan.target} confidence={result.score}"
            )
        )
    return result
