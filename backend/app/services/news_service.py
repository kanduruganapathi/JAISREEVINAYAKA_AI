from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import random
import re
from typing import Any
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

POSITIVE_KEYWORDS = {
    "upgrade",
    "surge",
    "beat",
    "growth",
    "strong",
    "rally",
    "expands",
    "profit",
    "outperform",
    "buy",
    "bullish",
    "breakout",
}

NEGATIVE_KEYWORDS = {
    "downgrade",
    "falls",
    "plunge",
    "weak",
    "miss",
    "lawsuit",
    "fraud",
    "probe",
    "selloff",
    "bearish",
    "loss",
    "warning",
}

RISK_KEYWORDS = {
    "fraud",
    "probe",
    "lawsuit",
    "volatile",
    "downgrade",
    "regulatory",
    "default",
    "penalty",
    "investigation",
}


class NewsService:
    _cache: dict[str, tuple[datetime, dict[str, Any]]] = {}
    _ttl = timedelta(minutes=10)

    def _rss_url(self, symbol: str) -> str:
        query = quote_plus(f"{symbol} NSE stock market news")
        return (
            "https://news.google.com/rss/search"
            f"?q={query}+when:2d&hl=en-IN&gl=IN&ceid=IN:en"
        )

    def _headline_score(self, headline: str) -> float:
        text = headline.lower()
        positives = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        negatives = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
        score = 0.5 + (positives - negatives) * 0.09
        return max(0.0, min(1.0, score))

    def _collect_risk_flags(self, headlines: list[str]) -> list[str]:
        flags: set[str] = set()
        for h in headlines:
            l = h.lower()
            for kw in RISK_KEYWORDS:
                if kw in l:
                    flags.add(f"News risk keyword detected: {kw}")
        return sorted(flags)

    def _fallback_snapshot(self, symbol: str, reason: str = "live-news-unavailable") -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        seed = sum(ord(ch) for ch in symbol)
        random.seed(seed)
        score = round(random.uniform(0.38, 0.71), 2)
        if score >= 0.62:
            sentiment = "positive"
        elif score <= 0.44:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        headlines = [
            f"{symbol}: market participants monitor intraday momentum and liquidity zones",
            f"{symbol}: traders focus on breakout validation and event-driven volatility",
            f"{symbol}: options positioning suggests tactical setup selection",
        ]

        risk_flags = ["Live feed unavailable; using fallback estimate."]

        return {
            "symbol": symbol,
            "timestamp": now,
            "sentiment": sentiment,
            "score": score,
            "headlines": headlines,
            "risk_flags": risk_flags,
            "source": "fallback",
            "mode": reason,
        }

    def _fetch_live(self, symbol: str, max_items: int = 6) -> dict[str, Any]:
        url = self._rss_url(symbol)
        with httpx.Client(timeout=4.5, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()

        root = ET.fromstring(response.text)
        items = root.findall(".//item")
        if not items:
            raise ValueError("No live news items returned")

        headlines: list[str] = []
        articles: list[dict[str, str]] = []

        for item in items[:max_items]:
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            # Remove source suffix often appended as " - Source"
            title = re.sub(r"\s+-\s+[^-]+$", "", title).strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            headlines.append(title)
            articles.append({"title": title, "link": link, "published": pub})

        if not headlines:
            raise ValueError("No valid headlines in RSS payload")

        scores = [self._headline_score(h) for h in headlines]
        avg_score = sum(scores) / len(scores)

        if avg_score >= 0.57:
            sentiment = "positive"
        elif avg_score <= 0.43:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sentiment": sentiment,
            "score": round(avg_score, 2),
            "headlines": headlines,
            "articles": articles,
            "risk_flags": self._collect_risk_flags(headlines),
            "source": "google-news-rss",
            "mode": "live",
        }

    def summarize(self, symbol: str, force_live: bool = False) -> dict[str, Any]:
        key = symbol.upper().strip()
        now = datetime.now(timezone.utc)

        if not force_live:
            cached = self._cache.get(key)
            if cached and (now - cached[0]) < self._ttl:
                payload = dict(cached[1])
                payload["mode"] = "cache"
                return payload

        try:
            payload = self._fetch_live(key)
            self._cache[key] = (now, payload)
            return payload
        except Exception as exc:
            logger.debug("Live news fetch failed for %s: %s", key, exc)
            fallback = self._fallback_snapshot(key)
            self._cache[key] = (now, fallback)
            return fallback
