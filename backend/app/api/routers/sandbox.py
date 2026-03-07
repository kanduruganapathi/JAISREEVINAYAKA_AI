from fastapi import APIRouter


router = APIRouter()


@router.get("/api/sandbox")
def sandbox_root() -> dict:
    return {
        "status": "ok",
        "message": "Sandbox compatibility endpoint. Use /api/v1/* for main API routes.",
    }


@router.get("/api/sandbox/get_day_candles")
def sandbox_day_candles(symbol: str = "NIFTY", interval: str = "1d") -> dict:
    return {
        "status": "ok",
        "symbol": symbol,
        "interval": interval,
        "message": "Compatibility placeholder endpoint. Use /api/v1/analysis/run instead.",
        "candles": [],
    }
