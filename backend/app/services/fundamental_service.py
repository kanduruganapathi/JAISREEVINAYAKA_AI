from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

from app.core.config import get_settings


@dataclass
class FundamentalService:
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    @staticmethod
    def _symbol_to_yahoo(symbol: str) -> str:
        s = symbol.strip().upper()
        if s in {"NIFTY", "NIFTY50"}:
            return "^NSEI"
        if s in {"BANKNIFTY"}:
            return "^NSEBANK"
        if s in {"SENSEX"}:
            return "^BSESN"
        if s.startswith("^") or s.endswith(".NS") or s.endswith(".BO"):
            return s
        return f"{s}.NS"

    @staticmethod
    def _as_pct(value: float | None) -> float | None:
        if value is None:
            return None
        if abs(value) <= 1.5:
            return value * 100.0
        return value

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            v = float(value)
            if v != v:  # NaN guard
                return None
            return v
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fallback_metrics(symbol: str) -> dict[str, float]:
        seed = sum(ord(ch) for ch in symbol)
        rng = random.Random(seed)
        return {
            "pe": round(rng.uniform(12.0, 38.0), 2),
            "roe_pct": round(rng.uniform(8.0, 28.0), 2),
            "debt_to_equity": round(rng.uniform(0.1, 1.3), 2),
            "revenue_growth_pct": round(rng.uniform(-8.0, 24.0), 2),
            "earnings_growth_pct": round(rng.uniform(-12.0, 28.0), 2),
            "profit_margin_pct": round(rng.uniform(6.0, 27.0), 2),
        }

    def _score_metrics(self, metrics: dict[str, float]) -> tuple[float, str, str]:
        pe = metrics.get("pe", 24.0)
        roe = metrics.get("roe_pct", 12.0)
        debt_to_equity = metrics.get("debt_to_equity", 0.9)
        rev_growth = metrics.get("revenue_growth_pct", 0.0)
        eps_growth = metrics.get("earnings_growth_pct", 0.0)
        margin = metrics.get("profit_margin_pct", 10.0)

        score = 0.5
        notes: list[str] = []

        if roe >= 18:
            score += 0.18
            notes.append("strong ROE")
        elif roe >= 14:
            score += 0.1
            notes.append("healthy ROE")
        elif roe < 10:
            score -= 0.1
            notes.append("weak ROE")

        if debt_to_equity <= 0.5:
            score += 0.14
            notes.append("low leverage")
        elif debt_to_equity >= 1.0:
            score -= 0.14
            notes.append("high leverage")

        if rev_growth >= 10:
            score += 0.1
            notes.append("strong revenue growth")
        elif rev_growth < 0:
            score -= 0.1
            notes.append("negative revenue growth")

        if eps_growth >= 10:
            score += 0.11
            notes.append("strong earnings growth")
        elif eps_growth < 0:
            score -= 0.11
            notes.append("negative earnings growth")

        if margin >= 15:
            score += 0.1
            notes.append("strong margin")
        elif margin < 8:
            score -= 0.08
            notes.append("weak margin")

        if pe <= 22:
            score += 0.07
            notes.append("reasonable valuation")
        elif pe >= 34:
            score -= 0.08
            notes.append("expensive valuation")

        score = max(0.0, min(1.0, score))
        signal = "bullish" if score >= 0.62 else "bearish" if score <= 0.42 else "neutral"
        summary = (
            f"PE {pe:.1f}, ROE {roe:.1f}%, D/E {debt_to_equity:.2f}, "
            f"Rev {rev_growth:.1f}%, EPS {eps_growth:.1f}%, Margin {margin:.1f}%"
        )
        if notes:
            summary += f" ({', '.join(notes[:3])})"
        return score, signal, summary

    def summarize(self, symbol: str) -> dict[str, Any]:
        if symbol in self._cache:
            return self._cache[symbol]

        mode = get_settings().market_data_mode.lower().strip()
        metrics: dict[str, float] | None = None
        source = "synthetic-fallback"
        run_mode = "fallback"

        if mode != "synthetic":
            try:
                import yfinance as yf  # type: ignore

                ticker = yf.Ticker(self._symbol_to_yahoo(symbol))
                info = ticker.info or {}
                pe = self._safe_float(info.get("trailingPE") or info.get("forwardPE"))
                roe_raw = self._safe_float(info.get("returnOnEquity"))
                de_raw = self._safe_float(info.get("debtToEquity"))
                rev_growth_raw = self._safe_float(info.get("revenueGrowth"))
                eps_growth_raw = self._safe_float(info.get("earningsGrowth"))
                margin_raw = self._safe_float(info.get("profitMargins"))

                if any(
                    x is not None
                    for x in [pe, roe_raw, de_raw, rev_growth_raw, eps_growth_raw, margin_raw]
                ):
                    metrics = {
                        "pe": pe if pe is not None else 24.0,
                        "roe_pct": self._as_pct(roe_raw) if roe_raw is not None else 12.0,
                        "debt_to_equity": (de_raw / 100.0) if de_raw is not None and de_raw > 10 else (de_raw if de_raw is not None else 0.9),
                        "revenue_growth_pct": self._as_pct(rev_growth_raw) if rev_growth_raw is not None else 0.0,
                        "earnings_growth_pct": self._as_pct(eps_growth_raw) if eps_growth_raw is not None else 0.0,
                        "profit_margin_pct": self._as_pct(margin_raw) if margin_raw is not None else 10.0,
                    }
                    source = "yfinance"
                    run_mode = "live"
            except Exception:
                metrics = None

        if metrics is None:
            metrics = self._fallback_metrics(symbol)

        score, signal, summary = self._score_metrics(metrics)
        payload = {
            "score": round(score, 2),
            "signal": signal,
            "summary": summary,
            "meta": {
                "mode": run_mode,
                "source": source,
                "pe": f"{metrics['pe']:.1f}",
                "roe": f"{metrics['roe_pct']:.1f}",
                "de": f"{metrics['debt_to_equity']:.2f}",
                "rev_growth": f"{metrics['revenue_growth_pct']:.1f}",
                "eps_growth": f"{metrics['earnings_growth_pct']:.1f}",
                "margin": f"{metrics['profit_margin_pct']:.1f}",
            },
        }
        self._cache[symbol] = payload
        return payload
