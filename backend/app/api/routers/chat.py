from fastapi import APIRouter

from app.models.chat import ChatRequest, ChatResponse
from app.services.intelligence import MarketIntelligenceService

router = APIRouter()
intelligence = MarketIntelligenceService()


@router.post("/chat/query", response_model=ChatResponse)
async def query_chat(req: ChatRequest) -> ChatResponse:
    answer, sources = await intelligence.answer(req.question, req.context)
    return ChatResponse(answer=answer, sources=sources)
