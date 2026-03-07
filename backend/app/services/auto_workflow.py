from __future__ import annotations

from datetime import datetime, timezone
import math

from app.core.config import get_settings
from app.models.scanner import StockScanRequest, StockScanResult
from app.models.strategy import BacktestRequest, StrategyRule
from app.models.trading import OrderRequest
from app.models.workflow import (
    AutoBacktestSummary,
    AutoGateResult,
    AutoOrderResult,
    AutoPaperWorkflowItem,
    AutoPaperWorkflowRequest,
    AutoPaperWorkflowResponse,
    AutoRiskPlan,
    AutoWorkflowSummary,
)
from app.services.backtest import BacktestService
from app.services.groww_client import GrowwBrokerClient
from app.services.market_data import DataProvider
from app.services.risk import pre_trade_checks
from app.services.scanner import StockScannerService


class AutoPaperWorkflowService:
    def __init__(self) -> None:
        self.scanner = StockScannerService()
        self.backtest = BacktestService()
        self.broker = GrowwBrokerClient()
        self.data = DataProvider()

    @staticmethod
    def _strategy_presets() -> dict[str, dict[str, float]]:
        return {
            "smc_breakout": {
                "bull_rsi_min": 48.0,
                "bear_rsi_max": 52.0,
                "require_displacement": 1.0,
                "min_histogram_strength": 0.01,
            },
            "ema_cross": {
                "fast_ema": 18.0,
                "slow_ema": 50.0,
                "confirm_price_above_ema": 1.0,
                "trend_gap_bps": 6.0,
            },
            "rsi_reversion": {
                "oversold": 30.0,
                "overbought": 70.0,
                "exit_rsi": 50.0,
                "neutral_band": 4.0,
            },
            "multi_timeframe_breakout": {
                "breakout_lookback": 20.0,
                "breakout_buffer_bps": 5.0,
            },
            "smc_liquidity_reversal": {
                "require_choch": 1.0,
                "long_rsi_floor": 34.0,
                "short_rsi_cap": 66.0,
                "min_body_atr_ratio": 0.45,
                "zone_recent_window": 30.0,
            },
            "fvg_ob_retest": {
                "require_displacement": 1.0,
                "min_body_atr_ratio": 0.35,
                "zone_recent_window": 30.0,
            },
            "volume_displacement_breakout": {
                "breakout_lookback": 24.0,
                "volume_multiplier": 1.35,
                "breakout_buffer_bps": 5.0,
                "min_body_atr_ratio": 0.65,
            },
            "premium_discount_reversion": {
                "long_rsi_max": 45.0,
                "short_rsi_min": 55.0,
                "level_threshold": 0.0035,
                "zone_recent_window": 30.0,
            },
            "hybrid_confluence_intraday": {
                "news_score": 0.5,
                "fundamental_score": 0.5,
                "long_threshold": 3.4,
                "short_threshold": 3.4,
                "zone_recent_window": 30.0,
            },
        }

    def _strategy_params_for(self, item: StockScanResult, strategy_name: str) -> dict[str, float]:
        params = dict(self._strategy_presets()[strategy_name])
        if strategy_name == "hybrid_confluence_intraday":
            params["news_score"] = float(item.news.score)
            params["fundamental_score"] = float(item.fundamental.score)
            # Increase confidence threshold when signal quality is weak.
            weak_quality = (
                item.news.score < 0.52
                or item.fundamental.score < 0.5
                or item.technical.score < 0.55
                or item.breakout.score < 0.52
            )
            if weak_quality:
                params["long_threshold"] = 3.8
                params["short_threshold"] = 3.8
        return params

    def _choose_strategy(self, item: StockScanResult) -> tuple[str, dict[str, float]]:
        if (
            item.news.score >= 0.6
            and item.fundamental.score >= 0.55
            and item.technical.score >= 0.58
            and item.breakout.score >= 0.55
        ):
            name = "hybrid_confluence_intraday"
            return name, self._strategy_params_for(item, name)

        if item.breakout.score >= 0.72 and item.technical.score >= 0.6:
            name = "volume_displacement_breakout"
            return name, self._strategy_params_for(item, name)

        if item.technical.score >= 0.62 and item.breakout.score >= 0.55:
            name = "fvg_ob_retest"
            return name, self._strategy_params_for(item, name)

        if item.action == "watch" and item.bias == "neutral":
            name = "premium_discount_reversion"
            return name, self._strategy_params_for(item, name)

        if item.news.signal != item.technical.signal and item.technical.signal != "neutral":
            name = "smc_liquidity_reversal"
            return name, self._strategy_params_for(item, name)

        if item.technical.score >= 0.65:
            name = "ema_cross"
            return name, self._strategy_params_for(item, name)

        name = "smc_breakout"
        return name, self._strategy_params_for(item, name)

    def _strategy_candidates(self, item: StockScanResult) -> list[tuple[str, dict[str, float]]]:
        preferred_name, _ = self._choose_strategy(item)
        order = [
            preferred_name,
            "hybrid_confluence_intraday",
            "volume_displacement_breakout",
            "fvg_ob_retest",
            "smc_liquidity_reversal",
            "premium_discount_reversion",
            "smc_breakout",
            "ema_cross",
            "rsi_reversion",
            "multi_timeframe_breakout",
        ]
        deduped: list[str] = []
        for name in order:
            if name not in deduped:
                deduped.append(name)
        return [(name, self._strategy_params_for(item, name)) for name in deduped]

    def _score_backtest(self, bt: AutoBacktestSummary) -> float:
        # Favor robust systems: positive return + sharpe + sufficient sample size.
        trade_factor = min(1.0, bt.trades / 12.0)
        return (
            bt.total_return_pct * 0.5
            + bt.win_rate_pct * 0.25
            + bt.sharpe * 12.0
            - bt.max_drawdown_pct * 0.2
            + trade_factor * 10.0
        )

    @staticmethod
    def _resolve_side(item: StockScanResult) -> str | None:
        if item.action == "buy":
            return "buy"
        if item.action == "sell":
            return "sell"
        if item.bias == "bullish":
            return "buy"
        if item.bias == "bearish":
            return "sell"
        return None

    def _build_risk_plan(
        self,
        item: StockScanResult,
        req: AutoPaperWorkflowRequest,
    ) -> AutoRiskPlan | None:
        side = self._resolve_side(item)
        if side is None:
            return None

        last_close = float(item.technical_snapshot.get("last_close", 0.0))
        atr_14 = float(item.technical_snapshot.get("atr_14", 0.0))
        if last_close <= 0:
            return None

        stop_distance = max(0.1, atr_14 * 0.8, last_close * 0.0035)
        risk_capital = req.initial_capital * (req.risk_per_trade_pct / 100.0)
        qty_by_risk = int(math.floor(risk_capital / stop_distance))
        qty_by_risk = max(1, qty_by_risk)

        settings = get_settings()
        max_qty_by_notional = int(math.floor(settings.max_order_notional / last_close))
        if max_qty_by_notional <= 0:
            return None

        qty = max(1, min(qty_by_risk, max_qty_by_notional))
        notional = qty * last_close
        return AutoRiskPlan(
            side=side, qty=qty, entry_price=round(last_close, 2), stop_distance=round(stop_distance, 2), notional=round(notional, 2)
        )

    @staticmethod
    def _build_gate(
        item: StockScanResult,
        backtest: AutoBacktestSummary,
        req: AutoPaperWorkflowRequest,
        risk_plan: AutoRiskPlan | None,
    ) -> AutoGateResult:
        reasons: list[str] = []

        if item.overall_score < req.min_scanner_score:
            reasons.append(
                f"Scanner score {item.overall_score:.2f} below threshold {req.min_scanner_score:.2f}."
            )
        if backtest.win_rate_pct < req.min_backtest_win_rate:
            reasons.append(
                f"Backtest win rate {backtest.win_rate_pct:.2f}% below {req.min_backtest_win_rate:.2f}%."
            )
        if backtest.total_return_pct < req.min_backtest_return_pct:
            reasons.append(
                f"Backtest return {backtest.total_return_pct:.2f}% below {req.min_backtest_return_pct:.2f}%."
            )
        if backtest.sharpe < req.min_backtest_sharpe:
            reasons.append(
                f"Backtest Sharpe {backtest.sharpe:.2f} below {req.min_backtest_sharpe:.2f}."
            )
        if backtest.trades < req.min_backtest_trades:
            reasons.append(
                f"Backtest trades {backtest.trades} below minimum {req.min_backtest_trades}."
            )
        if req.require_directional_action and item.action == "watch":
            reasons.append("Scanner action is WATCH; directional action required.")
        if risk_plan is None:
            reasons.append("Risk plan unavailable (qty or side could not be resolved).")

        return AutoGateResult(passed=not reasons, reasons=reasons)

    async def run(self, req: AutoPaperWorkflowRequest) -> AutoPaperWorkflowResponse:
        scan_req = StockScanRequest(
            universe=req.universe,
            symbols=req.symbols,
            timeframe=req.timeframe,
            top_n=req.top_n,
            include_news=req.include_news,
            include_fundamental=req.include_fundamental,
            include_breakout=req.include_breakout,
            include_technical=req.include_technical,
        )
        scan = self.scanner.run(scan_req)

        results: list[AutoPaperWorkflowItem] = []
        qualified_for_paper = 0
        paper_orders = 0

        for item in scan.results:
            best_strategy_name = "smc_breakout"
            best_strategy_params: dict[str, float] = {}
            best_bt_summary: AutoBacktestSummary | None = None
            best_bt_score = float("-inf")

            for strategy_name, strategy_params in self._strategy_candidates(item):
                bt_resp = self.backtest.run(
                    BacktestRequest(
                        symbol=item.symbol,
                        segment="equity",
                        candles=self.data.get_candles(item.symbol, req.timeframe, req.backtest_lookback_candles),
                        timeframe=req.timeframe,
                        lookback_candles=req.backtest_lookback_candles,
                        initial_capital=req.initial_capital,
                        commission_per_trade=20.0,
                        slippage_bps=5.0,
                        rule=StrategyRule(name=strategy_name, params=strategy_params),
                    )
                )
                bt_summary = AutoBacktestSummary(
                    total_return_pct=bt_resp.total_return_pct,
                    win_rate_pct=bt_resp.win_rate_pct,
                    max_drawdown_pct=bt_resp.max_drawdown_pct,
                    sharpe=bt_resp.sharpe,
                    trades=len(bt_resp.trades),
                )
                bt_score = self._score_backtest(bt_summary)
                if best_bt_summary is None or bt_score > best_bt_score:
                    best_bt_summary = bt_summary
                    best_bt_score = bt_score
                    best_strategy_name = strategy_name
                    best_strategy_params = strategy_params

            bt_summary = best_bt_summary or AutoBacktestSummary(
                total_return_pct=0.0,
                win_rate_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe=0.0,
                trades=0,
            )

            risk_plan = self._build_risk_plan(item, req)
            gate = self._build_gate(item, bt_summary, req, risk_plan)

            order_summary: AutoOrderResult | None = None
            if gate.passed:
                qualified_for_paper += 1

            if gate.passed and paper_orders < req.max_paper_trades and risk_plan is not None:
                settings = get_settings()
                ok, check_msg = pre_trade_checks(
                    notional=risk_plan.notional,
                    mode="paper",
                    max_order_notional=settings.max_order_notional,
                    live_enabled=settings.live_trading_enabled,
                )
                if ok:
                    order_payload = await self.broker.place_order(
                        OrderRequest(
                            symbol=item.symbol,
                            segment="equity",
                            side=risk_plan.side,
                            qty=risk_plan.qty,
                            order_type="market",
                            product_type="intraday",
                            mode="paper",
                        )
                    )
                    order_summary = AutoOrderResult(
                        order_id=str(order_payload.get("order_id", "")),
                        status=str(order_payload.get("status", "simulated")),
                        mode=str(order_payload.get("mode", "paper")),
                        message=str(order_payload.get("message", "")),
                    )
                    paper_orders += 1
                else:
                    gate.passed = False
                    gate.reasons.append(check_msg)

            results.append(
                AutoPaperWorkflowItem(
                    symbol=item.symbol,
                    rank=item.rank,
                    scanner_score=item.overall_score,
                    scanner_bias=item.bias,
                    scanner_action=item.action,
                    chosen_strategy=best_strategy_name,
                    strategy_params=best_strategy_params,
                    backtest=bt_summary,
                    gate=gate,
                    risk_plan=risk_plan,
                    order=order_summary,
                )
            )

        rejected = len(results) - qualified_for_paper
        return AutoPaperWorkflowResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            timeframe=req.timeframe,
            universe=req.universe,
            summary=AutoWorkflowSummary(
                scanned=scan.summary.scanned,
                selected_for_backtest=len(results),
                qualified_for_paper=qualified_for_paper,
                paper_orders=paper_orders,
                rejected=max(0, rejected),
            ),
            results=results,
        )
