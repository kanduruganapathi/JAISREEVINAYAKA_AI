from __future__ import annotations

from datetime import datetime, timezone
import random


class NewsService:
    def summarize(self, symbol: str) -> dict:
        # Replace with real providers/NLP sentiment service in production.
        now = datetime.now(timezone.utc).isoformat()
        seed = sum(ord(ch) for ch in symbol)
        random.seed(seed)
        score = round(random.uniform(0.35, 0.78), 2)
        if score >= 0.62:
            sentiment = "positive"
        elif score <= 0.45:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        headlines = [
            f"{symbol}: institutional flow trend and sector momentum in focus",
            f"{symbol}: traders watching breakout levels ahead of event volatility",
            f"{symbol}: options positioning indicates short-term directional bias",
        ]

        risk_flags = []
        if sentiment == "negative":
            risk_flags.append("Negative headline momentum in near-term news flow.")

        return {
            "symbol": symbol,
            "timestamp": now,
            "sentiment": sentiment,
            "score": score,
            "headlines": headlines,
            "risk_flags": risk_flags,
        }
