from __future__ import annotations

from datetime import datetime, timedelta, timezone


class EventService:
    def upcoming(self, symbol: str) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "symbol": symbol,
            "events": [
                {
                    "name": "Earnings / Corporate Event Window",
                    "time": (now + timedelta(days=7)).isoformat(),
                    "impact": "medium",
                },
                {
                    "name": "Macro Volatility Session",
                    "time": (now + timedelta(days=2)).isoformat(),
                    "impact": "high",
                },
            ],
        }
