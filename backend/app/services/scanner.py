from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.analysis import Candle
from app.models.scanner import (
    IntradayPlan,
    MarketSnapshot,
    ScanFactor,
    StockScanRequest,
    StockScanResponse,
    StockScanResult,
    StockScanSummary,
    StrategyValidation,
)
from app.models.strategy import BacktestRequest, StrategyRule
from app.services.backtest import BacktestService
from app.services.fundamental_service import FundamentalService
from app.services.indicators import compute_indicator_pack
from app.services.market_data import DataProvider
from app.services.news_service import NewsService
from app.services.smc import detect_market_structure

NIFTY50_SYMBOLS = [
    "ADANIENT",
    "ADANIPORTS",
    "APOLLOHOSP",
    "ASIANPAINT",
    "AXISBANK",
    "BAJAJ-AUTO",
    "BAJFINANCE",
    "BAJAJFINSV",
    "BEL",
    "BHARTIARTL",
    "BPCL",
    "BRITANNIA",
    "CIPLA",
    "COALINDIA",
    "DRREDDY",
    "EICHERMOT",
    "ETERNAL",
    "GRASIM",
    "HCLTECH",
    "HDFCBANK",
    "HDFCLIFE",
    "HEROMOTOCO",
    "HINDALCO",
    "HINDUNILVR",
    "ICICIBANK",
    "INDUSINDBK",
    "INFY",
    "ITC",
    "JIOFIN",
    "JSWSTEEL",
    "KOTAKBANK",
    "LT",
    "M&M",
    "MARUTI",
    "NESTLEIND",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "RELIANCE",
    "SBILIFE",
    "SHRIRAMFIN",
    "SBIN",
    "SUNPHARMA",
    "TCS",
    "TATACONSUM",
    "TATAMOTORS",
    "TATASTEEL",
    "TECHM",
    "TITAN",
    "ULTRACEMCO",
    "WIPRO",
]


class StockScannerService:
    def __init__(self) -> None:
        self.data = DataProvider()
        self.news = NewsService()
        self.fundamental = FundamentalService()
        self.backtest = BacktestService()

    @staticmethod
    def _neutral_factor(summary: str, mode: str) -> ScanFactor:
        return ScanFactor(
            score=0.5,
            signal="neutral",
            summary=summary,
            meta={"mode": mode, "source": "none", "timestamp": ""},
        )

    def _fundamental_factor(self, symbol: str) -> ScanFactor:
        snapshot = self.fundamental.summarize(symbol)
        return ScanFactor(
            score=float(snapshot.get("score", 0.5)),
            signal=str(snapshot.get("signal", "neutral")),
            summary=str(snapshot.get("summary", "Fundamental data unavailable.")),
            meta={str(k): str(v) for k, v in dict(snapshot.get("meta", {})).items()},
        )

    def _news_factor(self, symbol: str, force_live: bool = False) -> ScanFactor:
        snapshot = self.news.summarize(symbol, force_live=force_live)
        sentiment = snapshot.get("sentiment", "neutral")
        score = float(snapshot.get("score", 0.5))
        signal = "bullish" if sentiment == "positive" else "bearish" if sentiment == "negative" else "neutral"
        summary = "; ".join(snapshot.get("headlines", [])[:2]) or "No major headline edge."
        return ScanFactor(
            score=round(score, 2),
            signal=signal,
            summary=summary,
            meta={
                "mode": str(snapshot.get("mode", "unknown")),
                "source": str(snapshot.get("source", "unknown")),
                "timestamp": str(snapshot.get("timestamp", "")),
            },
        )

    @staticmethod
    def _session_window(timeframe: str) -> int:
        if timeframe == "5m":
            return 75
        if timeframe == "15m":
            return 26
        if timeframe == "30m":
            return 13
        if timeframe == "1h":
            return 7
        if timeframe == "1d":
            return 5
        return 26

    def _technical_factor(self, candles: list[Candle], timeframe: str) -> tuple[ScanFactor, dict[str, float], dict, MarketSnapshot, float]:
        indicators = compute_indicator_pack(candles)
        smc = detect_market_structure(candles)
        last = candles[-1]
        prev_close = candles[-2].close if len(candles) >= 2 else last.close

        recent_window = max(5, min(20, len(candles) - 1))
        avg_vol_recent = sum(c.volume for c in candles[-recent_window:]) / recent_window
        avg_vol_baseline = sum(c.volume for c in candles[-(recent_window * 3) : -recent_window]) / max(
            1, recent_window * 2
        )
        volume_ratio = avg_vol_recent / max(avg_vol_baseline, 1e-9)

        atr = max(indicators.get("atr_14", 0.0), 1e-6)
        trend_strength = abs(indicators["ema_20"] - indicators["ema_50"]) / atr
        rsi = indicators["rsi_14"]
        hist = indicators["histogram"]

        score = 0.5
        if indicators["ema_20"] > indicators["ema_50"]:
            score += 0.14
        else:
            score -= 0.14

        if trend_strength >= 1.0:
            score += 0.09
        elif trend_strength < 0.45:
            score -= 0.07

        if hist > 0.02:
            score += 0.08
        elif hist < -0.02:
            score -= 0.08

        if indicators["ema_20"] >= indicators["ema_50"] and 50 <= rsi <= 68:
            score += 0.08
        elif indicators["ema_20"] < indicators["ema_50"] and 32 <= rsi <= 50:
            score += 0.08
        elif rsi >= 78 or rsi <= 22:
            score -= 0.1

        bos = smc.get("bos", "none")
        choch = smc.get("choch", "none")
        if bos == "bullish_bos":
            score += 0.11
        elif bos == "bearish_bos":
            score -= 0.11
        if choch == "bullish_choch":
            score += 0.05
        elif choch == "bearish_choch":
            score -= 0.05

        if volume_ratio >= 1.2:
            score += 0.06
        elif volume_ratio < 0.75:
            score -= 0.04

        score = max(0.0, min(1.0, score))
        signal = "bullish" if score > 0.6 else "bearish" if score < 0.42 else "neutral"
        summary = (
            f"EMA20/50 {indicators['ema_20']:.2f}/{indicators['ema_50']:.2f}, "
            f"RSI {rsi:.1f}, Hist {hist:.3f}, BOS {bos}, Vol x{volume_ratio:.2f}"
        )

        session_window = min(len(candles), self._session_window(timeframe))
        session_slice = candles[-session_window:]
        day_high = max(c.high for c in session_slice)
        day_low = min(c.low for c in session_slice)
        open_price = session_slice[0].open
        close_price = last.close
        change_pct = ((close_price - prev_close) / max(prev_close, 1e-9)) * 100.0

        snapshot = {
            "ema_20": round(indicators["ema_20"], 4),
            "ema_50": round(indicators["ema_50"], 4),
            "rsi_14": round(rsi, 4),
            "histogram": round(hist, 4),
            "atr_14": round(atr, 4),
            "volume_ratio": round(volume_ratio, 4),
            "trend_strength": round(trend_strength, 4),
            "last_open": round(last.open, 4),
            "last_close": round(close_price, 4),
            "prev_close": round(prev_close, 4),
            "last_high": round(last.high, 4),
            "last_low": round(last.low, 4),
            "day_high": round(day_high, 4),
            "day_low": round(day_low, 4),
            "change_pct": round(change_pct, 4),
        }

        market_snapshot = MarketSnapshot(
            live_price=round(close_price, 4),
            open_price=round(open_price, 4),
            close_price=round(close_price, 4),
            prev_close=round(prev_close, 4),
            day_high=round(day_high, 4),
            day_low=round(day_low, 4),
            change_pct=round(change_pct, 4),
            volume=round(last.volume, 4),
        )
        return ScanFactor(score=round(score, 2), signal=signal, summary=summary), snapshot, smc, market_snapshot, volume_ratio

    def _breakout_factor(self, snapshot: dict[str, float], candles: list[Candle], volume_ratio: float) -> ScanFactor:
        last_close = snapshot["last_close"]
        high_20 = max(c.high for c in candles[-21:-1])
        low_20 = min(c.low for c in candles[-21:-1])
        buffer = snapshot["atr_14"] * 0.15

        score = 0.5
        signal = "neutral"
        summary = "No active breakout edge."

        if last_close > high_20 + buffer and volume_ratio >= 1.1:
            score = 0.86
            signal = "bullish"
            summary = f"Confirmed upside breakout above {high_20:.2f} with volume x{volume_ratio:.2f}."
        elif last_close < low_20 - buffer and volume_ratio >= 1.1:
            score = 0.86
            signal = "bearish"
            summary = f"Confirmed downside breakdown below {low_20:.2f} with volume x{volume_ratio:.2f}."
        else:
            dist_high = (high_20 - last_close) / max(last_close, 1.0)
            dist_low = (last_close - low_20) / max(last_close, 1.0)
            near_high = dist_high < 0.0045
            near_low = dist_low < 0.0045
            if near_high:
                score = 0.65
                signal = "bullish"
                summary = "Price is compressing near breakout resistance; wait for 15m close + retest."
            elif near_low:
                score = 0.65
                signal = "bearish"
                summary = "Price is compressing near breakdown support; wait for displacement confirmation."

        return ScanFactor(score=round(score, 2), signal=signal, summary=summary)

    def _intraday_plan(
        self,
        overall_score: float,
        bias: str,
        snapshot: dict[str, float],
        breakout: ScanFactor,
    ) -> IntradayPlan:
        last = snapshot["last_close"]
        atr = max(snapshot.get("atr_14", 0.0), 0.1)

        if bias == "bullish":
            entry = f"{last * 1.0008:.2f} - {last * 1.0025:.2f} after 5m pullback hold"
            stop = f"{last - atr * 0.9:.2f}"
            t1 = f"{last + atr * 1.1:.2f}"
            t2 = f"{last + atr * 2.0:.2f}"
            invalidation = "Cancel if entry zone breaks with bearish CHOCH."
            setup = "Trend continuation from demand/FVG with volume support."
            direction = "long"
        elif bias == "bearish":
            entry = f"{last * 0.9992:.2f} - {last * 0.9975:.2f} after 5m weak retest"
            stop = f"{last + atr * 0.9:.2f}"
            t1 = f"{last - atr * 1.1:.2f}"
            t2 = f"{last - atr * 2.0:.2f}"
            invalidation = "Cancel if entry zone reclaims with bullish CHOCH."
            setup = "Breakdown continuation from supply/OB with weak rebound."
            direction = "short"
        else:
            entry = "Wait for range breakout with 15m close + retest confirmation"
            stop = "Opposite side of range boundary"
            t1 = "1R"
            t2 = "2R"
            invalidation = "No trade if structure remains balanced/choppy."
            setup = "No directional edge yet. Keep in watchlist."
            direction = "neutral"

        rr = 1.7
        if breakout.signal != "neutral":
            rr = 2.0
        if overall_score >= 0.75:
            rr += 0.25

        return IntradayPlan(
            direction=direction,
            setup=setup,
            entry_zone=entry,
            stop_loss=stop,
            targets=[t1, t2],
            invalidation=invalidation,
            rr_estimate=round(rr, 2),
        )

    @staticmethod
    def _aggregate(
        technical: ScanFactor,
        breakout: ScanFactor,
        fundamental: ScanFactor,
        news: ScanFactor,
    ) -> tuple[float, str, str]:
        score = (
            technical.score * 0.34
            + breakout.score * 0.22
            + fundamental.score * 0.24
            + news.score * 0.20
        )

        bullish_votes = sum(1 for f in [technical, breakout, fundamental, news] if f.signal == "bullish")
        bearish_votes = sum(1 for f in [technical, breakout, fundamental, news] if f.signal == "bearish")

        if bullish_votes > bearish_votes:
            bias = "bullish"
            action = "buy" if score >= 0.6 else "watch"
        elif bearish_votes > bullish_votes:
            bias = "bearish"
            action = "sell" if score >= 0.6 else "watch"
        else:
            bias = "neutral"
            action = "watch"

        return round(max(0.0, min(1.0, score)), 2), bias, action

    @staticmethod
    def _strategy_candidates(news_score: float, fundamental_score: float) -> list[tuple[str, dict[str, float]]]:
        risk = {
            "stop_atr_mult": 1.0,
            "take_profit_rr": 1.8,
            "trail_atr_mult": 0.9,
            "risk_pct": 1.0,
            "max_notional_pct": 0.25,
            "cooldown_bars": 3.0,
            "max_hold_bars": 28.0,
            "min_hold_bars": 2.0,
        }
        return [
            (
                "hybrid_confluence_intraday",
                {
                    "news_score": news_score,
                    "fundamental_score": fundamental_score,
                    "long_threshold": 3.8,
                    "short_threshold": 3.8,
                    "min_regime_score": 0.4,
                    **risk,
                },
            ),
            (
                "regime_adaptive_breakout",
                {
                    "breakout_lookback": 22.0,
                    "breakout_buffer_bps": 5.0,
                    "volume_multiplier": 1.2,
                    "trend_regime_threshold": 0.9,
                    **risk,
                },
            ),
            (
                "trend_pullback_confluence",
                {
                    "pullback_atr": 1.0,
                    "min_volume_ratio": 0.8,
                    "max_rsi_long": 68.0,
                    "min_rsi_short": 32.0,
                    **risk,
                },
            ),
            ("liquidity_trap_reversal", {"min_wick_ratio": 0.32, "min_body_atr_ratio": 0.2, **risk}),
            (
                "volume_displacement_breakout",
                {
                    "breakout_lookback": 24.0,
                    "volume_multiplier": 1.35,
                    "breakout_buffer_bps": 5.0,
                    "min_body_atr_ratio": 0.65,
                    **risk,
                },
            ),
            (
                "smc_breakout",
                {
                    "bull_rsi_min": 52.0,
                    "bear_rsi_max": 48.0,
                    "require_displacement": 1.0,
                    "min_histogram_strength": 0.03,
                    **risk,
                },
            ),
            ("fvg_ob_retest", {"require_displacement": 1.0, "min_body_atr_ratio": 0.35, **risk}),
        ]

    def _strategy_validation(
        self,
        symbol: str,
        timeframe: str,
        candles: list[Candle],
        news_score: float,
        fundamental_score: float,
    ) -> StrategyValidation:
        best: StrategyValidation | None = None
        best_score = float("-inf")

        for name, params in self._strategy_candidates(news_score, fundamental_score):
            bt = self.backtest.run(
                BacktestRequest(
                    symbol=symbol,
                    segment="equity",
                    candles=candles,
                    timeframe=timeframe,
                    lookback_candles=len(candles),
                    initial_capital=100000.0,
                    commission_per_trade=10.0,
                    slippage_bps=3.0,
                    rule=StrategyRule(name=name, params=params),
                )
            )
            trades = len(bt.trades)
            quality = (
                bt.total_return_pct * 1.4
                + bt.sharpe * 10.0
                + bt.win_rate_pct * 0.12
                - bt.max_drawdown_pct * 0.25
                + min(trades, 40) * 0.08
            )

            if bt.total_return_pct >= 0.0 and bt.win_rate_pct >= 40.0 and bt.sharpe >= 0.0 and trades >= 6:
                status = "pass"
                reason = "Positive return with stable win rate/sharpe."
            elif bt.total_return_pct >= -0.35 and bt.win_rate_pct >= 30.0 and trades >= 4:
                status = "watch"
                reason = "Near breakeven quality; use tighter execution filters."
            else:
                status = "fail"
                reason = "Weak expectancy on current regime."

            if get_settings().market_data_mode.lower().strip() == "synthetic" and status == "fail":
                status = "watch"
                reason = "Synthetic feed mode: use MARKET_DATA_MODE=live for real strategy validation."

            candidate = StrategyValidation(
                strategy=name,
                total_return_pct=round(bt.total_return_pct, 2),
                win_rate_pct=round(bt.win_rate_pct, 2),
                sharpe=round(bt.sharpe, 2),
                trades=trades,
                status=status,
                reason=reason,
            )
            if quality > best_score:
                best_score = quality
                best = candidate

        return best or StrategyValidation(
            strategy="none",
            total_return_pct=0.0,
            win_rate_pct=0.0,
            sharpe=0.0,
            trades=0,
            status="fail",
            reason="Strategy validation unavailable.",
        )

    def run(self, req: StockScanRequest) -> StockScanResponse:
        symbols = req.symbols if req.universe == "custom" and req.symbols else NIFTY50_SYMBOLS
        staged: list[dict] = []
        candles_by_symbol: dict[str, list[Candle]] = {}

        for symbol in symbols:
            candles = self.data.get_candles(symbol, req.timeframe, 220)
            candles_by_symbol[symbol] = candles
            technical, snapshot, _smc, market_snapshot, volume_ratio = self._technical_factor(candles, req.timeframe)
            breakout = self._breakout_factor(snapshot, candles, volume_ratio)

            if not req.include_technical:
                technical = self._neutral_factor("Technical check disabled.", "disabled")
            if not req.include_breakout:
                breakout = self._neutral_factor("Breakout check disabled.", "disabled")

            provisional_score, provisional_bias, provisional_action = self._aggregate(
                technical=technical,
                breakout=breakout,
                fundamental=self._neutral_factor("Fundamental check pending.", "deferred"),
                news=self._neutral_factor("News check pending.", "deferred"),
            )

            staged.append(
                {
                    "symbol": symbol,
                    "technical": technical,
                    "breakout": breakout,
                    "snapshot": snapshot,
                    "market_snapshot": market_snapshot,
                    "provisional_score": provisional_score,
                    "provisional_bias": provisional_bias,
                    "provisional_action": provisional_action,
                }
            )

        staged_ranked = sorted(staged, key=lambda x: x["provisional_score"], reverse=True)
        deep_count = min(len(symbols), max(req.top_n * 3, 20))
        deep_symbols = {x["symbol"] for x in staged_ranked[:deep_count]}
        items: list[StockScanResult] = []

        for row in staged_ranked:
            symbol = row["symbol"]
            technical = row["technical"]
            breakout = row["breakout"]
            snapshot = row["snapshot"]
            market_snapshot = row["market_snapshot"]

            if req.include_fundamental and symbol in deep_symbols:
                fundamental = self._fundamental_factor(symbol)
            elif req.include_fundamental:
                fundamental = self._neutral_factor(
                    "Fundamental deep analysis prioritized for top-ranked candidates.",
                    "deferred",
                )
            else:
                fundamental = self._neutral_factor("Fundamental check disabled.", "disabled")

            if req.include_news and symbol in deep_symbols:
                news = self._news_factor(symbol, force_live=True)
            elif req.include_news:
                news = self._neutral_factor("Live news prioritized for top-ranked candidates only.", "deferred")
            else:
                news = self._neutral_factor("News check disabled.", "disabled")

            overall_score, bias, action = self._aggregate(
                technical=technical,
                breakout=breakout,
                fundamental=fundamental,
                news=news,
            )

            items.append(
                StockScanResult(
                    symbol=symbol,
                    rank=0,
                    overall_score=overall_score,
                    bias=bias,
                    action=action,
                    technical=technical,
                    breakout=breakout,
                    fundamental=fundamental,
                    news=news,
                    technical_snapshot=snapshot,
                    market_snapshot=market_snapshot,
                    strategy_validation=None,
                    intraday_plan=self._intraday_plan(overall_score, bias, snapshot, breakout),
                )
            )

        ranked = sorted(items, key=lambda x: x.overall_score, reverse=True)
        capped = ranked[: max(1, min(req.top_n, len(ranked)))]

        for idx, item in enumerate(capped, start=1):
            item.rank = idx
            candles = candles_by_symbol.get(item.symbol, [])
            if candles and len(candles) >= 120:
                validation = self._strategy_validation(
                    symbol=item.symbol,
                    timeframe=req.timeframe,
                    candles=candles,
                    news_score=item.news.score,
                    fundamental_score=item.fundamental.score,
                )
                item.strategy_validation = validation
                if validation.status == "fail":
                    item.action = "watch"
                elif validation.status == "pass" and item.bias == "bullish":
                    item.action = "buy"
                elif validation.status == "pass" and item.bias == "bearish":
                    item.action = "sell"

        bullish = sum(1 for i in capped if i.bias == "bullish")
        bearish = sum(1 for i in capped if i.bias == "bearish")
        neutral = sum(1 for i in capped if i.bias == "neutral")
        high_conf = sum(
            1
            for i in capped
            if i.overall_score >= 0.68 and (i.strategy_validation is None or i.strategy_validation.status != "fail")
        )

        return StockScanResponse(
            universe=req.universe,
            timeframe=req.timeframe,
            generated_at=datetime.now(timezone.utc).isoformat(),
            summary=StockScanSummary(
                scanned=len(symbols),
                bullish=bullish,
                bearish=bearish,
                neutral=neutral,
                high_confidence=high_conf,
            ),
            results=capped,
        )
