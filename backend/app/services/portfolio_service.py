from __future__ import annotations

from app.models.portfolio import PortfolioRequest, PortfolioResponse, PositionMetrics


class PortfolioService:
    def analyze(self, req: PortfolioRequest) -> PortfolioResponse:
        metrics: list[PositionMetrics] = []
        invested = 0.0
        total = 0.0

        for p in req.positions:
            invested_val = p.qty * p.avg_price
            market_val = p.qty * p.last_price
            pnl = market_val - invested_val
            invested += invested_val
            total += market_val

            metrics.append(
                PositionMetrics(
                    symbol=p.symbol,
                    market_value=round(market_val, 2),
                    invested_value=round(invested_val, 2),
                    pnl=round(pnl, 2),
                    pnl_pct=round((pnl / invested_val * 100) if invested_val else 0.0, 2),
                    weight_pct=0.0,
                )
            )

        if not req.positions:
            total = req.capital

        for m in metrics:
            m.weight_pct = round((m.market_value / total * 100) if total else 0.0, 2)

        concentration = max((m.weight_pct for m in metrics), default=0.0)
        total_pnl = total - invested
        total_pnl_pct = (total_pnl / invested * 100) if invested else 0.0

        # Light VaR approximation for baseline monitoring
        var95 = round(total * 0.02, 2)

        recs = []
        if concentration > 35:
            recs.append("Reduce concentration risk: single position > 35% of portfolio.")
        if total_pnl_pct < -10:
            recs.append("Portfolio drawdown breached -10%. Shift to defensive sizing.")
        if not recs:
            recs.append("Risk allocation is balanced for current portfolio state.")

        return PortfolioResponse(
            total_value=round(total, 2),
            invested_value=round(invested, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            concentration_risk_pct=round(concentration, 2),
            value_at_risk_95=var95,
            recommendations=recs,
            positions=metrics,
        )
