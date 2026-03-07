from __future__ import annotations

import httpx

from app.core.config import get_settings


class MarketIntelligenceService:
    async def answer(self, question: str, context: dict | None = None) -> tuple[str, list[str]]:
        settings = get_settings()
        context = context or {}

        if not settings.gemini_api_key:
            return (
                "Gemini key missing. Baseline answer: use multi-timeframe confirmation, strict risk caps, and paper-test before live execution.",
                ["local-fallback"],
            )

        prompt = (
            "You are a market intelligence assistant for Indian markets. "
            "Answer with risk-first reasoning, no guarantee claims.\n"
            f"Context: {context}\n"
            f"Question: {question}"
        )

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
        }

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "No response")
                )
                return text, ["gemini-1.5-flash"]
            except Exception:
                return (
                    "Intelligence model unavailable now. Retry shortly; meanwhile keep exposure small and wait for confirmation zones.",
                    ["gemini-error-fallback"],
                )
