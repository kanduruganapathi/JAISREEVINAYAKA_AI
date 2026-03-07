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

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 500},
        }

        model_candidates = [
            "gemini-2.0-flash",
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
        ]

        async with httpx.AsyncClient(timeout=20) as client:
            for model in model_candidates:
                try:
                    url = (
                        "https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{model}:generateContent?key={settings.gemini_api_key}"
                    )
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "No response")
                    )
                    return text, [model]
                except Exception:
                    continue

            return (
                "Intelligence model unavailable now. Retry shortly; meanwhile keep exposure small and wait for confirmation zones.",
                ["gemini-error-fallback"],
            )
