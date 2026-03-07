from __future__ import annotations

import math

from app.models.analysis import Candle
from app.models.strategy import BacktestRequest, BacktestResponse, EquityPoint, TradeRecord
from app.services.strategy_engine import StrategyEngine


class BacktestService:
    def __init__(self) -> None:
        self.engine = StrategyEngine()

    def run(self, req: BacktestRequest) -> BacktestResponse:
        if len(req.candles) < 80:
            return BacktestResponse(
                symbol=req.symbol,
                total_return_pct=0.0,
                win_rate_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe=0.0,
                trades=[],
                equity_curve=[EquityPoint(ts=c.ts, equity=req.initial_capital) for c in req.candles],
            )

        equity = req.initial_capital
        peak = req.initial_capital
        max_dd = 0.0

        trade_open = None
        trades: list[TradeRecord] = []
        curve: list[EquityPoint] = []
        returns = []

        for i in range(60, len(req.candles)):
            window: list[Candle] = req.candles[: i + 1]
            c = req.candles[i]
            signal = self.engine.generate_signal(window, req.rule)

            if trade_open is None and signal in {"long", "short"}:
                qty = max(1.0, equity * 0.1 / c.close)
                trade_open = {
                    "side": signal,
                    "entry": c.close,
                    "qty": qty,
                    "entry_ts": c.ts,
                }

            elif trade_open is not None:
                side = trade_open["side"]
                entry = trade_open["entry"]
                qty = trade_open["qty"]

                exit_trade = signal == "flat" or signal != side
                if exit_trade:
                    gross = (c.close - entry) * qty if side == "long" else (entry - c.close) * qty
                    slippage = c.close * qty * (req.slippage_bps / 10000)
                    pnl = gross - req.commission_per_trade - slippage
                    pnl_pct = pnl / max(1.0, entry * qty)
                    equity += pnl
                    returns.append(pnl_pct)

                    trades.append(
                        TradeRecord(
                            entry_ts=trade_open["entry_ts"],
                            exit_ts=c.ts,
                            side=side,
                            entry=entry,
                            exit=c.close,
                            qty=qty,
                            pnl=round(pnl, 2),
                            pnl_pct=round(pnl_pct * 100, 2),
                        )
                    )
                    trade_open = None

            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak else 0.0
            max_dd = max(max_dd, dd)
            curve.append(EquityPoint(ts=c.ts, equity=round(equity, 2)))

        wins = sum(1 for t in trades if t.pnl > 0)
        win_rate = (wins / len(trades) * 100) if trades else 0.0
        total_return = ((equity - req.initial_capital) / req.initial_capital * 100) if req.initial_capital else 0.0

        avg_ret = sum(returns) / len(returns) if returns else 0.0
        std_ret = (sum((r - avg_ret) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 0.0
        sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret else 0.0

        return BacktestResponse(
            symbol=req.symbol,
            total_return_pct=round(total_return, 2),
            win_rate_pct=round(win_rate, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            sharpe=round(sharpe, 2),
            trades=trades,
            equity_curve=curve,
        )
