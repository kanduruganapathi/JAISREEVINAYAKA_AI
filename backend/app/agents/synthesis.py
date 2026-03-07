from __future__ import annotations

from app.models.analysis import AgentSignal, RiskSnapshot, TradePlan


class SynthesisAgent:
    def synthesize(self, signals: list[AgentSignal], last_price: float, risk: RiskSnapshot) -> tuple[str, float, TradePlan, str]:
        weighted = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
        for s in signals:
            weighted[s.bias] += s.confidence

        consensus = max(weighted, key=weighted.get)
        total = sum(weighted.values())
        score = (weighted[consensus] / total) if total else 0.5

        action = "hold"
        if consensus == "bullish" and score > 0.4:
            action = "buy"
        elif consensus == "bearish" and score > 0.4:
            action = "sell"

        if action == "buy":
            entry = last_price
            stop = last_price * (1 - risk.stop_loss_pct)
            target = last_price * (1 + risk.take_profit_pct)
            rationale = "Bullish confluence across agents with risk-defined entry."
            regime = "risk_on"
        elif action == "sell":
            entry = last_price
            stop = last_price * (1 + risk.stop_loss_pct)
            target = last_price * (1 - risk.take_profit_pct)
            rationale = "Bearish confluence across agents with risk-defined entry."
            regime = "risk_off"
        else:
            entry = None
            stop = None
            target = None
            rationale = "No clean confluence. Wait for valid pullback/BOS confirmation."
            regime = "neutral"

        plan = TradePlan(
            action=action,
            entry=round(entry, 2) if entry else None,
            stop_loss=round(stop, 2) if stop else None,
            target=round(target, 2) if target else None,
            rationale=rationale,
        )
        return consensus, round(score, 2), plan, regime
