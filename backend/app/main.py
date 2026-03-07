from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import analysis, backtest, chat, health, portfolio, sandbox, trading
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
app.include_router(backtest.router, prefix="/api/v1", tags=["backtest"])
app.include_router(trading.router, prefix="/api/v1", tags=["trading"])
app.include_router(portfolio.router, prefix="/api/v1", tags=["portfolio"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(sandbox.router, tags=["compat"])
