from __future__ import annotations

from datetime import datetime, timezone
import random

from app.models.scanner import (
    IntradayPlan,
    ScanFactor,
    StockScanRequest,
    StockScanResponse,
    StockScanResult,
    StockScanSummary,
)
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

    def _fundamental_factor(self, symbol: str) -> ScanFactor:
        seed = sum(ord(c) for c in symbol)
        random.seed(seed)
        roe = random.uniform(8, 29)
        eps_growth = random.uniform(-0.12, 0.33)
        debt_to_equity = random.uniform(0.05, 1.15)

        score = 0.5
        if roe > 16:
            score += 0.2
        if eps_growth > 0.11:
            score += 0.15
        if debt_to_equity < 0.5:
            score += 0.12
        if eps_growth < 0:
            score -= 0.14
        if debt_to_equity > 0.9:
            score -= 0.1

        score = max(0.0, min(1.0, score))
        signal = "bullish" if score > 0.62 else "bearish" if score < 0.42 else "neutral"
        summary = (
            f"ROE {roe:.1f}%, EPS growth {eps_growth*100:.1f}%, D/E {debt_to_equity:.2f}."
        )
        return ScanFactor(score=round(score, 2), signal=signal, summary=summary)

    def _news_factor(self, symbol: str, force_live: bool = False) -> ScanFactor:
        snapshot = self.news.summarize(symbol, force_live=force_live)
        sentiment = snapshot.get("sentiment", "neutral")
        score = float(snapshot.get("score", 0.5))
        signal = "bullish" if sentiment == "positive" else "bearish" if sentiment == "negative" else "neutral"
        summary = "; ".join(snapshot.get("headlines", [])[:2])
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

    def _technical_factor(self, symbol: str, timeframe: str) -> tuple[ScanFactor, dict[str, float], dict]:
        candles = self.data.get_candles(symbol, timeframe, 220)
        indicators = compute_indicator_pack(candles)
        smc = detect_market_structure(candles)

        score = 0.5
        if indicators["ema_20"] > indicators["ema_50"]:
            score += 0.15
        else:
            score -= 0.15

        if indicators["histogram"] > 0:
            score += 0.08
        else:
            score -= 0.08

        if 48 <= indicators["rsi_14"] <= 65:
            score += 0.08
        elif indicators["rsi_14"] > 75 or indicators["rsi_14"] < 28:
            score -= 0.08

        if smc.get("bos") == "bullish_bos":
            score += 0.12
        elif smc.get("bos") == "bearish_bos":
            score -= 0.12

        score = max(0.0, min(1.0, score))
        signal = "bullish" if score > 0.6 else "bearish" if score < 0.42 else "neutral"

        summary = (
            f"EMA20/50={indicators['ema_20']:.2f}/{indicators['ema_50']:.2f}, "
            f"RSI={indicators['rsi_14']:.1f}, BOS={smc.get('bos', 'none')}"
        )

        snapshot = {
            "ema_20": round(indicators["ema_20"], 4),
            "ema_50": round(indicators["ema_50"], 4),
            "rsi_14": round(indicators["rsi_14"], 4),
            "histogram": round(indicators["histogram"], 4),
            "atr_14": round(indicators["atr_14"], 4),
            "last_close": round(candles[-1].close, 4),
            "last_high": round(candles[-1].high, 4),
            "last_low": round(candles[-1].low, 4),
        }
        return ScanFactor(score=round(score, 2), signal=signal, summary=summary), snapshot, smc

    def _breakout_factor(self, snapshot: dict[str, float], candles: list) -> ScanFactor:
        last_close = snapshot["last_close"]
        high_20 = max(c.high for c in candles[-21:-1])
        low_20 = min(c.low for c in candles[-21:-1])

        score = 0.5
        signal = "neutral"

        if last_close > high_20:
            score = 0.82
            signal = "bullish"
            summary = f"Price closed above 20-candle high ({high_20:.2f}) breakout confirmation."
        elif last_close < low_20:
            score = 0.82
            signal = "bearish"
            summary = f"Price closed below 20-candle low ({low_20:.2f}) breakdown confirmation."
        else:
            dist_high = (high_20 - last_close) / max(last_close, 1)
            dist_low = (last_close - low_20) / max(last_close, 1)
            near_high = dist_high < 0.004
            near_low = dist_low < 0.004
            if near_high:
                score = 0.64
                signal = "bullish"
                summary = "Price is compressing near breakout zone; watch volume trigger."
            elif near_low:
                score = 0.64
                signal = "bearish"
                summary = "Price is near breakdown zone; watch for displacement candle."
            else:
                score = 0.45
                signal = "neutral"
                summary = "No active breakout edge."

        return ScanFactor(score=round(score, 2), signal=signal, summary=summary)

    def _intraday_plan(
        self,
        symbol: str,
        overall_score: float,
        bias: str,
        snapshot: dict[str, float],
        breakout: ScanFactor,
    ) -> IntradayPlan:
        last = snapshot["last_close"]
        atr = max(snapshot.get("atr_14", 0.0), 0.1)

        if bias == "bullish":
            entry = f"{last * 1.001:.2f} - {last * 1.003:.2f} on 5m confirmation"
            stop = f"{last - atr * 0.8:.2f}"
            t1 = f"{last + atr * 1.2:.2f}"
            t2 = f"{last + atr * 2.0:.2f}"
            invalidation = "Abort if breakout candle is fully retraced in next 2 candles."
            setup = "Breakout-pullback continuation with volume expansion and VWAP hold."
            direction = "long"
        elif bias == "bearish":
            entry = f"{last * 0.999:.2f} - {last * 0.997:.2f} on 5m confirmation"
            stop = f"{last + atr * 0.8:.2f}"
            t1 = f"{last - atr * 1.2:.2f}"
            t2 = f"{last - atr * 2.0:.2f}"
            invalidation = "Abort if breakdown candle is fully retraced in next 2 candles."
            setup = "Breakdown-retest continuation with weak rebound and supply pressure."
            direction = "short"
        else:
            entry = "Wait for range breakout with 15m candle close and retest"
            stop = "Opposite side of opening range"
            t1 = "1R"
            t2 = "2R"
            invalidation = "No trade if structure remains range-bound after first hour."
            setup = "No edge yet. Keep in watchlist for clean directional trigger."
            direction = "neutral"

        rr = 2.0 if breakout.signal != "neutral" else 1.3
        if overall_score > 0.75:
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

    def _aggregate(self, technical: ScanFactor, breakout: ScanFactor, fundamental: ScanFactor, news: ScanFactor) -> tuple[float, str, str]:
        score = (
            technical.score * 0.34
            + breakout.score * 0.28
            + fundamental.score * 0.2
            + news.score * 0.18
        )

        bullish_votes = sum(1 for f in [technical, breakout, fundamental, news] if f.signal == "bullish")
        bearish_votes = sum(1 for f in [technical, breakout, fundamental, news] if f.signal == "bearish")

        if bullish_votes > bearish_votes:
            bias = "bullish"
            action = "buy" if score >= 0.55 else "watch"
        elif bearish_votes > bullish_votes:
            bias = "bearish"
            action = "sell" if score >= 0.55 else "watch"
        else:
            bias = "neutral"
            action = "watch"

        return round(max(0.0, min(1.0, score)), 2), bias, action

    def run(self, req: StockScanRequest) -> StockScanResponse:
        symbols = req.symbols if req.universe == "custom" and req.symbols else NIFTY50_SYMBOLS
        items: list[StockScanResult] = []

        staged: list[dict] = []
        neutral_news = ScanFactor(
            score=0.5,
            signal="neutral",
            summary="News score pending live pull.",
            meta={"mode": "deferred", "source": "none", "timestamp": ""},
        )

        for symbol in symbols:
            candles = self.data.get_candles(symbol, req.timeframe, 220)
            technical, snapshot, _smc = self._technical_factor(symbol, req.timeframe)
            breakout = self._breakout_factor(snapshot, candles)
            fundamental = self._fundamental_factor(symbol)
            if not req.include_fundamental:
                fundamental = ScanFactor(
                    score=0.5,
                    signal="neutral",
                    summary="Fundamental check disabled.",
                    meta={"mode": "disabled"},
                )
            if not req.include_breakout:
                breakout = ScanFactor(
                    score=0.5,
                    signal="neutral",
                    summary="Breakout check disabled.",
                    meta={"mode": "disabled"},
                )
            if not req.include_technical:
                technical = ScanFactor(
                    score=0.5,
                    signal="neutral",
                    summary="Technical check disabled.",
                    meta={"mode": "disabled"},
                )

            provisional_score, provisional_bias, provisional_action = self._aggregate(
                technical,
                breakout,
                fundamental,
                neutral_news,
            )

            staged.append(
                {
                    "symbol": symbol,
                    "candles": candles,
                    "technical": technical,
                    "breakout": breakout,
                    "fundamental": fundamental,
                    "snapshot": snapshot,
                    "provisional_score": provisional_score,
                    "provisional_bias": provisional_bias,
                    "provisional_action": provisional_action,
                }
            )

        staged_ranked = sorted(staged, key=lambda x: x["provisional_score"], reverse=True)
        if req.include_news:
            if len(symbols) <= 20:
                news_symbols = {x["symbol"] for x in staged_ranked}
            else:
                priority_count = min(len(symbols), max(req.top_n * 3, 20))
                news_symbols = {x["symbol"] for x in staged_ranked[:priority_count]}
        else:
            news_symbols = set()

        for row in staged_ranked:
            symbol = row["symbol"]
            technical = row["technical"]
            breakout = row["breakout"]
            fundamental = row["fundamental"]
            snapshot = row["snapshot"]

            if req.include_news and symbol in news_symbols:
                news = self._news_factor(symbol, force_live=True)
            elif req.include_news:
                news = ScanFactor(
                    score=0.5,
                    signal="neutral",
                    summary="Live news prioritized for top-ranked candidates only.",
                    meta={"mode": "deferred", "source": "none", "timestamp": ""},
                )
            else:
                news = ScanFactor(
                    score=0.5,
                    signal="neutral",
                    summary="News check disabled.",
                    meta={"mode": "disabled"},
                )

            overall_score, bias, action = self._aggregate(technical, breakout, fundamental, news)
            intraday_plan = self._intraday_plan(symbol, overall_score, bias, snapshot, breakout)
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
                    intraday_plan=intraday_plan,
                )
            )

        ranked = sorted(items, key=lambda x: x.overall_score, reverse=True)
        capped = ranked[: max(1, min(req.top_n, len(ranked)))]

        for idx, item in enumerate(capped, start=1):
            item.rank = idx

        bullish = sum(1 for i in capped if i.bias == "bullish")
        bearish = sum(1 for i in capped if i.bias == "bearish")
        neutral = sum(1 for i in capped if i.bias == "neutral")
        high_conf = sum(1 for i in capped if i.overall_score >= 0.7)

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
