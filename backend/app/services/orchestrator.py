from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.agents.events import EventAgent
from app.agents.fundamental import FundamentalAgent
from app.agents.news import NewsAgent
from app.agents.risk import RiskAgent
from app.agents.smc import SMCPriceActionAgent
from app.agents.synthesis import SynthesisAgent
from app.agents.technical import TechnicalAgent
from app.models.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    MarketStructureSnapshot,
    StrategyIdea,
    TimeframeBias,
)
from app.services.indicators import compute_indicator_pack
from app.services.market_data import DataProvider
from app.services.risk import build_risk_snapshot
from app.services.smc import detect_market_structure


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self.data = DataProvider()
        self.synthesis = SynthesisAgent()
        self.fundamental = FundamentalAgent()
        self.technical = TechnicalAgent()
        self.news = NewsAgent()
        self.events = EventAgent()
        self.smc = SMCPriceActionAgent()
        self.risk_agent = RiskAgent()

    def _bias_from_score(self, score: int) -> tuple[str, float]:
        if score > 0:
            return "bullish", min(0.9, 0.52 + abs(score) * 0.1)
        if score < 0:
            return "bearish", min(0.9, 0.52 + abs(score) * 0.1)
        return "neutral", 0.5

    def _build_timeframe_biases(self, candles_by_tf: dict[str, list]) -> list[TimeframeBias]:
        biases: list[TimeframeBias] = []
        for tf, candles in candles_by_tf.items():
            ind = compute_indicator_pack(candles)
            smc = detect_market_structure(candles)

            score = 0
            if ind.get("ema_20", 0.0) > ind.get("ema_50", 0.0):
                score += 1
            else:
                score -= 1

            if ind.get("histogram", 0.0) > 0:
                score += 1
            else:
                score -= 1

            if smc.get("bos") == "bullish_bos":
                score += 1
            elif smc.get("bos") == "bearish_bos":
                score -= 1

            if smc.get("trend") == "uptrend":
                score += 1
            elif smc.get("trend") == "downtrend":
                score -= 1

            bias, confidence = self._bias_from_score(score)
            note = (
                f"Trend={smc.get('trend')} | BOS={smc.get('bos')} | RSI={round(ind.get('rsi_14', 0.0), 2)}"
            )
            biases.append(
                TimeframeBias(
                    timeframe=tf,
                    bias=bias,
                    confidence=round(confidence, 2),
                    note=note,
                )
            )
        return biases

    def _build_market_structure_snapshot(self, smc: dict) -> MarketStructureSnapshot:
        return MarketStructureSnapshot(
            trend=smc.get("trend", "neutral"),
            bos=smc.get("bos", "none"),
            choch=smc.get("choch", "none"),
            support=[float(x) for x in smc.get("support", [])],
            resistance=[float(x) for x in smc.get("resistance", [])],
            premium_zone=smc.get("premium_zone"),
            discount_zone=smc.get("discount_zone"),
            liquidity_sweeps=smc.get("liquidity_sweeps", []),
            fvg_zones=smc.get("fvg_zones", []),
            order_blocks=smc.get("order_blocks", []),
        )

    def _options_strategy_ideas(
        self,
        req: AnalysisRequest,
        last_price: float,
        consensus: str,
        score: float,
        stop: float,
        target: float,
    ) -> list[StrategyIdea]:
        expiry = "current weekly expiry"
        ideas: list[StrategyIdea] = []

        if consensus == "bullish":
            ideas.append(
                StrategyIdea(
                    name="ATM CE Momentum Scalping",
                    instrument=f"{req.symbol} ATM CE ({expiry})",
                    direction="bullish",
                    setup="Trade only after 5m pullback + reclaim with momentum candle.",
                    entry_trigger=f"Spot breaks and closes above {round(last_price * 1.002, 2)} on 5m.",
                    stop_rule=f"Spot below {round(stop, 2)} or option premium drawdown 25%.",
                    targets=[
                        f"Partial at {round(last_price * 1.004, 2)}",
                        f"Final at {round(target, 2)} or trail 9EMA",
                    ],
                    confidence=score,
                    timeframe=req.primary_timeframe,
                )
            )
            ideas.append(
                StrategyIdea(
                    name="Bull Call Spread Intraday",
                    instrument=f"Buy ATM CE + Sell OTM CE ({expiry})",
                    direction="bullish",
                    setup="Use when directional bias is bullish but volatility is elevated.",
                    entry_trigger="Deploy after first valid BOS and no bearish CHOCH on 15m.",
                    stop_rule="Close spread if spot loses session VWAP with volume.",
                    targets=["Book at 35-55% spread value expansion", "Hard exit before final 20 min"],
                    confidence=max(0.45, round(score - 0.08, 2)),
                    timeframe="15m + 5m",
                )
            )
            ideas.append(
                StrategyIdea(
                    name="FVG Re-entry CE",
                    instrument=f"{req.symbol} ITM/ATM CE ({expiry})",
                    direction="bullish",
                    setup="Enter only when price retraces into bullish FVG/discount and prints rejection wick.",
                    entry_trigger="5m displacement candle after retracement into demand/FVG.",
                    stop_rule="Exit if 5m closes below entry FVG low.",
                    targets=["Scale at 1R", "Trail balance below 9EMA till structure break"],
                    confidence=max(0.46, round(score - 0.04, 2)),
                    timeframe="5m execution, 15m structure",
                )
            )
            ideas.append(
                StrategyIdea(
                    name="Expiry Momentum CE + Hedge PE",
                    instrument=f"Buy ATM CE and tiny OTM PE hedge ({expiry})",
                    direction="bullish",
                    setup="For high momentum expiry sessions where reversal spikes are frequent.",
                    entry_trigger="Only after trend-day confirmation with successive higher lows.",
                    stop_rule="Kill setup if CE premium loses 28% from entry.",
                    targets=["Book 60% at 1.5R", "Carry 40% with trailing stop"],
                    confidence=max(0.44, round(score - 0.06, 2)),
                    timeframe="5m",
                )
            )
        elif consensus == "bearish":
            ideas.append(
                StrategyIdea(
                    name="ATM PE Momentum Scalping",
                    instrument=f"{req.symbol} ATM PE ({expiry})",
                    direction="bearish",
                    setup="Trade only after bearish retest failure and displacement candle.",
                    entry_trigger=f"Spot breaks and closes below {round(last_price * 0.998, 2)} on 5m.",
                    stop_rule=f"Spot above {round(stop, 2)} or option premium drawdown 25%.",
                    targets=[
                        f"Partial at {round(last_price * 0.996, 2)}",
                        f"Final at {round(target, 2)} or trail 9EMA",
                    ],
                    confidence=score,
                    timeframe=req.primary_timeframe,
                )
            )
            ideas.append(
                StrategyIdea(
                    name="Bear Put Spread Intraday",
                    instrument=f"Buy ATM PE + Sell OTM PE ({expiry})",
                    direction="bearish",
                    setup="Use when downside is expected but implied volatility can mean-revert.",
                    entry_trigger="Deploy after bearish BOS with failed bullish pullback.",
                    stop_rule="Close spread if spot reclaims session VWAP and holds for 2 candles.",
                    targets=["Book at 35-55% spread value expansion", "Hard exit before final 20 min"],
                    confidence=max(0.45, round(score - 0.08, 2)),
                    timeframe="15m + 5m",
                )
            )
            ideas.append(
                StrategyIdea(
                    name="FVG Re-entry PE",
                    instrument=f"{req.symbol} ITM/ATM PE ({expiry})",
                    direction="bearish",
                    setup="Enter on retrace into bearish FVG/supply followed by rejection close.",
                    entry_trigger="5m bearish displacement from premium zone/supply.",
                    stop_rule="Exit if 5m closes above entry FVG high.",
                    targets=["Scale at 1R", "Trail balance above 9EMA till structure break"],
                    confidence=max(0.46, round(score - 0.04, 2)),
                    timeframe="5m execution, 15m structure",
                )
            )
            ideas.append(
                StrategyIdea(
                    name="Expiry Momentum PE + Hedge CE",
                    instrument=f"Buy ATM PE and tiny OTM CE hedge ({expiry})",
                    direction="bearish",
                    setup="For heavy sell-off sessions where counter-trend spikes are violent.",
                    entry_trigger="Only after trend-day confirmation with lower highs sequence.",
                    stop_rule="Kill setup if PE premium loses 28% from entry.",
                    targets=["Book 60% at 1.5R", "Carry 40% with trailing stop"],
                    confidence=max(0.44, round(score - 0.06, 2)),
                    timeframe="5m",
                )
            )
        else:
            ideas.append(
                StrategyIdea(
                    name="Opening Range Breakout Wait-and-Trade",
                    instrument=f"{req.symbol} ATM straddle legs (select one side post-break)",
                    direction="neutral",
                    setup="No pre-commitment. Wait for clean ORB break and then trade only winning side.",
                    entry_trigger="Take side only after 15m breakout + retest confirmation.",
                    stop_rule="Invalidate on opposite ORB break or two-candle failure.",
                    targets=["1R at first impulse", "2R only if trend continuation confirms"],
                    confidence=max(0.4, round(score, 2)),
                    timeframe="15m + 5m",
                )
            )
            ideas.append(
                StrategyIdea(
                    name="Gamma Scalping Watch",
                    instrument=f"{req.symbol} near-ATM options pair ({expiry})",
                    direction="neutral",
                    setup="Stay hedged and deploy only when breakout confirms from compression.",
                    entry_trigger="No execution until 15m range break with volume surge.",
                    stop_rule="Flat position if re-entry into range persists for 3 candles.",
                    targets=["Quick 0.8R to 1.2R objective", "No overnight carry"],
                    confidence=max(0.38, round(score - 0.05, 2)),
                    timeframe="15m + 5m",
                )
            )

        return ideas

    def _equity_strategy_ideas(
        self,
        req: AnalysisRequest,
        last_price: float,
        consensus: str,
        score: float,
        stop: float,
        target: float,
    ) -> list[StrategyIdea]:
        if consensus == "bullish":
            return [
                StrategyIdea(
                    name="BOS Pullback Continuation",
                    instrument=req.symbol,
                    direction="bullish",
                    setup="Wait for bullish BOS and valid pullback into demand/OB.",
                    entry_trigger=f"15m close above {round(last_price * 1.0015, 2)} after pullback holds.",
                    stop_rule=f"Hard stop below {round(stop, 2)}",
                    targets=[f"First target {round(last_price * 1.006, 2)}", f"Final target {round(target, 2)}"],
                    confidence=score,
                    timeframe=req.primary_timeframe,
                )
            ]

        if consensus == "bearish":
            return [
                StrategyIdea(
                    name="Breakdown Retest Short",
                    instrument=req.symbol,
                    direction="bearish",
                    setup="Bearish BOS with weak retest into supply/mitigation block.",
                    entry_trigger=f"15m close below {round(last_price * 0.9985, 2)} with rising volume.",
                    stop_rule=f"Hard stop above {round(stop, 2)}",
                    targets=[f"First target {round(last_price * 0.994, 2)}", f"Final target {round(target, 2)}"],
                    confidence=score,
                    timeframe=req.primary_timeframe,
                )
            ]

        return [
            StrategyIdea(
                name="Range Rotation",
                instrument=req.symbol,
                direction="neutral",
                setup="No directional edge. Fade extremes only with strict mean-reversion conditions.",
                entry_trigger="Take setup only at support/resistance with rejection candle + low event risk.",
                stop_rule="Abort on displacement candle against position.",
                targets=["Book quickly at mid-range", "No overstay in chop"],
                confidence=max(0.4, score),
                timeframe=req.primary_timeframe,
            )
        ]

    def _build_strategy_ideas(
        self,
        req: AnalysisRequest,
        last_price: float,
        consensus: str,
        score: float,
        risk_stop_pct: float,
        risk_take_profit_pct: float,
    ) -> list[StrategyIdea]:
        stop_for_long = last_price * (1 - risk_stop_pct)
        stop_for_short = last_price * (1 + risk_stop_pct)
        target_for_long = last_price * (1 + risk_take_profit_pct)
        target_for_short = last_price * (1 - risk_take_profit_pct)

        if consensus == "bearish":
            stop = stop_for_short
            target = target_for_short
        else:
            stop = stop_for_long
            target = target_for_long

        if req.segment in {"intraday_options", "stock_options"}:
            return self._options_strategy_ideas(req, last_price, consensus, score, stop, target)
        return self._equity_strategy_ideas(req, last_price, consensus, score, stop, target)

    def _build_execution_checklist(
        self,
        req: AnalysisRequest,
        consensus: str,
        regime: str,
        timeframe_biases: list[TimeframeBias],
    ) -> list[str]:
        aligns = len([t for t in timeframe_biases if t.bias == consensus]) >= max(1, len(timeframe_biases) // 2)
        checklist = [
            "Confirm setup only after candle close; do not pre-empt breakout.",
            f"Primary timeframe {req.primary_timeframe} should align with at least one higher timeframe.",
            "Risk per trade <= 1% of deployable capital.",
            "Use fixed invalidation; no averaging losers.",
        ]

        if not aligns:
            checklist.append("Timeframe alignment is weak. Reduce position size by 30-50%.")

        if req.segment in {"intraday_options", "stock_options"}:
            checklist.extend(
                [
                    "Avoid first 5 minutes and avoid fresh entries in last 20 minutes.",
                    "Use ATM/near-ATM contracts with strong liquidity.",
                    "Exit failed setups quickly; option theta decay accelerates intraday.",
                    "For index options, avoid overtrading around macro event windows.",
                ]
            )
        else:
            checklist.extend(
                [
                    "Scale only after trade moves +1R in favor.",
                    "Do not chase if entry zone is missed by >0.4%.",
                ]
            )

        checklist.append(f"Regime tag: {regime}.")
        return checklist

    async def run(self, req: AnalysisRequest, capital: float = 100000.0) -> AnalysisResponse:
        timeframes = [req.primary_timeframe] + [t for t in req.secondary_timeframes if t != req.primary_timeframe]
        candles_by_tf = {}

        for tf in timeframes:
            candles_by_tf[tf] = req.candles if req.candles and tf == req.primary_timeframe else self.data.get_candles(req.symbol, tf)

        selected_agents = []
        if req.include_fundamental and req.segment not in {"intraday_options", "stock_options"}:
            selected_agents.append(self.fundamental)
        if req.include_technical:
            selected_agents.append(self.technical)
        if req.include_news:
            selected_agents.append(self.news)
        if req.include_events:
            selected_agents.append(self.events)
        if req.include_smc or req.include_price_action:
            selected_agents.append(self.smc)
        selected_agents.append(self.risk_agent)

        signals = await asyncio.gather(*[agent.run(req, candles_by_tf) for agent in selected_agents])

        primary = candles_by_tf[req.primary_timeframe]
        last_price = primary[-1].close
        ind = compute_indicator_pack(primary)
        smc_primary = detect_market_structure(primary)
        timeframe_biases = self._build_timeframe_biases(candles_by_tf)
        avg_conf = sum(s.confidence for s in signals) / len(signals)

        risk = build_risk_snapshot(
            capital=capital,
            price=last_price,
            volatility=ind.get("volatility", 0.2),
            confidence=avg_conf,
            segment=req.segment,
        )

        consensus, score, plan, regime = self.synthesis.synthesize(signals, last_price, risk)
        strategy_ideas = self._build_strategy_ideas(
            req=req,
            last_price=last_price,
            consensus=consensus,
            score=score,
            risk_stop_pct=risk.stop_loss_pct,
            risk_take_profit_pct=risk.take_profit_pct,
        )
        execution_checklist = self._build_execution_checklist(req, consensus, regime, timeframe_biases)

        return AnalysisResponse(
            symbol=req.symbol,
            segment=req.segment,
            regime=regime,
            score=score,
            consensus_bias=consensus,
            trade_plan=plan,
            risk=risk,
            indicator_snapshot={
                "ema_20": round(ind.get("ema_20", 0.0), 4),
                "ema_50": round(ind.get("ema_50", 0.0), 4),
                "rsi_14": round(ind.get("rsi_14", 0.0), 4),
                "macd": round(ind.get("macd", 0.0), 4),
                "signal": round(ind.get("signal", 0.0), 4),
                "histogram": round(ind.get("histogram", 0.0), 4),
                "atr_14": round(ind.get("atr_14", 0.0), 4),
                "volatility": round(ind.get("volatility", 0.0), 6),
            },
            timeframe_biases=timeframe_biases,
            market_structure=self._build_market_structure_snapshot(smc_primary),
            strategy_ideas=strategy_ideas,
            execution_checklist=execution_checklist,
            signals=signals,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
