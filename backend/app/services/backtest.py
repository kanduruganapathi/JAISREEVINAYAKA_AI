from __future__ import annotations

import math

from app.models.analysis import Candle
from app.models.strategy import BacktestRequest, BacktestResponse, EquityPoint, TradeRecord
from app.services.indicators import compute_indicator_pack
from app.services.strategy_engine import StrategyEngine


class BacktestService:
    def __init__(self) -> None:
        self.engine = StrategyEngine()

    @staticmethod
    def _param_float(req: BacktestRequest, key: str, default: float, min_value: float, max_value: float) -> float:
        raw = req.rule.params.get(key, default)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = default
        return max(min_value, min(max_value, val))

    @staticmethod
    def _param_int(req: BacktestRequest, key: str, default: int, min_value: int, max_value: int) -> int:
        raw = req.rule.params.get(key, default)
        try:
            val = int(float(raw))
        except (TypeError, ValueError):
            val = default
        return max(min_value, min(max_value, val))

    @staticmethod
    def _trade_pnl(side: str, entry: float, exit_price: float, qty: float) -> float:
        return (exit_price - entry) * qty if side == "long" else (entry - exit_price) * qty

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

        stop_atr_mult = self._param_float(req, "stop_atr_mult", 1.1, min_value=0.4, max_value=5.0)
        take_profit_rr = self._param_float(req, "take_profit_rr", 1.8, min_value=0.6, max_value=8.0)
        trailing_atr_mult = self._param_float(req, "trail_atr_mult", 0.9, min_value=0.2, max_value=5.0)
        risk_pct = self._param_float(req, "risk_pct", 1.0, min_value=0.2, max_value=5.0)
        max_notional_pct = self._param_float(req, "max_notional_pct", 0.25, min_value=0.05, max_value=1.0)
        min_stop_pct = self._param_float(req, "min_stop_pct", 0.0025, min_value=0.0005, max_value=0.03)
        max_hold_bars = self._param_int(req, "max_hold_bars", 28, min_value=4, max_value=250)
        min_hold_bars = self._param_int(req, "min_hold_bars", 2, min_value=0, max_value=50)
        cooldown_bars = self._param_int(req, "cooldown_bars", 3, min_value=0, max_value=120)

        trade_open = None
        trades: list[TradeRecord] = []
        curve: list[EquityPoint] = []
        returns = []
        cooldown = 0

        def close_trade(exit_price: float, exit_ts: str) -> None:
            nonlocal trade_open, equity
            if trade_open is None:
                return
            side = str(trade_open["side"])
            entry = float(trade_open["entry"])
            qty = float(trade_open["qty"])
            gross = self._trade_pnl(side, entry, exit_price, qty)
            slippage = exit_price * qty * (req.slippage_bps / 10000)
            pnl = gross - req.commission_per_trade - slippage
            pnl_pct = pnl / max(1.0, entry * qty)
            equity += pnl
            returns.append(pnl_pct)
            trades.append(
                TradeRecord(
                    entry_ts=str(trade_open["entry_ts"]),
                    exit_ts=exit_ts,
                    side=side,
                    entry=entry,
                    exit=exit_price,
                    qty=qty,
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct * 100, 2),
                )
            )
            trade_open = None

        for i in range(60, len(req.candles)):
            window: list[Candle] = req.candles[: i + 1]
            c = req.candles[i]
            signal = self.engine.generate_signal(window, req.rule)
            indicators = compute_indicator_pack(window)
            atr = max(indicators.get("atr_14", 0.0), c.close * min_stop_pct, 1e-6)

            if cooldown > 0:
                cooldown -= 1

            if trade_open is not None:
                side = str(trade_open["side"])
                entry = float(trade_open["entry"])
                qty = float(trade_open["qty"])
                hold_bars = int(trade_open["hold_bars"]) + 1
                trade_open["hold_bars"] = hold_bars

                if side == "long":
                    trade_open["best_price"] = max(float(trade_open["best_price"]), c.high)
                    trail_stop = float(trade_open["best_price"]) - trailing_atr_mult * atr
                    trade_open["stop"] = max(float(trade_open["stop"]), trail_stop)
                    stop_hit = c.low <= float(trade_open["stop"])
                    target_hit = c.high >= float(trade_open["target"])
                    if stop_hit:
                        close_trade(float(trade_open["stop"]), c.ts)
                        cooldown = cooldown_bars
                    elif target_hit:
                        close_trade(float(trade_open["target"]), c.ts)
                        cooldown = cooldown_bars
                    elif signal == "short":
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars
                    elif hold_bars >= max_hold_bars:
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars
                    elif signal == "flat" and hold_bars >= min_hold_bars:
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars
                else:
                    trade_open["best_price"] = min(float(trade_open["best_price"]), c.low)
                    trail_stop = float(trade_open["best_price"]) + trailing_atr_mult * atr
                    trade_open["stop"] = min(float(trade_open["stop"]), trail_stop)
                    stop_hit = c.high >= float(trade_open["stop"])
                    target_hit = c.low <= float(trade_open["target"])
                    if stop_hit:
                        close_trade(float(trade_open["stop"]), c.ts)
                        cooldown = cooldown_bars
                    elif target_hit:
                        close_trade(float(trade_open["target"]), c.ts)
                        cooldown = cooldown_bars
                    elif signal == "long":
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars
                    elif hold_bars >= max_hold_bars:
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars
                    elif signal == "flat" and hold_bars >= min_hold_bars:
                        close_trade(c.close, c.ts)
                        cooldown = cooldown_bars

            if trade_open is None and cooldown == 0 and signal in {"long", "short"}:
                stop_distance = max(stop_atr_mult * atr, c.close * min_stop_pct)
                risk_capital = max(0.0, equity * (risk_pct / 100.0))
                qty_by_risk = max(1, int(math.floor(risk_capital / max(stop_distance, 1e-9))))
                qty_by_notional = max(1, int(math.floor((equity * max_notional_pct) / max(c.close, 1e-9))))
                qty = float(max(1, min(qty_by_risk, qty_by_notional)))
                if signal == "long":
                    stop = c.close - stop_distance
                    target = c.close + stop_distance * take_profit_rr
                else:
                    stop = c.close + stop_distance
                    target = c.close - stop_distance * take_profit_rr
                trade_open = {
                    "side": signal,
                    "entry": c.close,
                    "qty": qty,
                    "entry_ts": c.ts,
                    "stop": stop,
                    "target": target,
                    "hold_bars": 0,
                    "best_price": c.close,
                }

            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak else 0.0
            max_dd = max(max_dd, dd)
            curve.append(EquityPoint(ts=c.ts, equity=round(equity, 2)))

        if trade_open is not None and req.candles:
            last_candle = req.candles[-1]
            close_trade(last_candle.close, last_candle.ts)
            curve.append(EquityPoint(ts=last_candle.ts, equity=round(equity, 2)))

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
