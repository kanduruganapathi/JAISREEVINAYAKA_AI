from __future__ import annotations

from app.models.analysis import RiskSnapshot


def build_risk_snapshot(
    capital: float,
    price: float,
    volatility: float,
    confidence: float,
    segment: str,
) -> RiskSnapshot:
    risk_budget_pct = 0.01 if segment in {"equity", "swing_stock"} else 0.007
    risk_budget = capital * risk_budget_pct

    stop_loss_pct = max(0.005, min(0.03, volatility / 8 if volatility else 0.012))
    take_profit_pct = stop_loss_pct * 2.2

    position_value = risk_budget / stop_loss_pct
    max_position_size = round(position_value / max(price, 1), 2)

    warnings = []
    if confidence < 0.55:
        warnings.append("Low confidence setup. Reduce size or skip trade.")
    if volatility > 0.45:
        warnings.append("High volatility regime detected.")
    if segment in {"intraday_options", "stock_options"}:
        warnings.append("Options gamma risk: keep hard stop and time-stop.")

    return RiskSnapshot(
        max_position_size=max_position_size,
        stop_loss_pct=round(stop_loss_pct, 4),
        take_profit_pct=round(take_profit_pct, 4),
        risk_reward_ratio=round(take_profit_pct / stop_loss_pct, 2),
        warnings=warnings,
    )


def pre_trade_checks(notional: float, mode: str, max_order_notional: float, live_enabled: bool) -> tuple[bool, str]:
    if mode == "live" and not live_enabled:
        return False, "Live trading is disabled by configuration."
    if notional > max_order_notional:
        return False, f"Order notional exceeds max allowed ({max_order_notional})."
    return True, "ok"
