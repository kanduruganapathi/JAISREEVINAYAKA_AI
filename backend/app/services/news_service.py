from __future__ import annotations

from datetime import datetime, timezone


class NewsService:
    def summarize(self, symbol: str) -> dict:
        # Plug in real news providers + NLP scoring.
        now = datetime.now(timezone.utc).isoformat()
        return {
            "symbol": symbol,
            "timestamp": now,
            "sentiment": "neutral",
            "score": 0.52,
            "headlines": [
                f"{symbol}: liquidity conditions stable across major venues",
                f"{symbol}: market awaits macro and policy signals",
            ],
            "risk_flags": [],
        }
