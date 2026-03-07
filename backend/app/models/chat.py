from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    context: dict | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
