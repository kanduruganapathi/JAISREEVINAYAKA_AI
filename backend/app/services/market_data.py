from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import random
from typing import Any

from app.core.config import get_settings
from app.models.analysis import Candle


@dataclass
class DataProvider:
    """Market data provider with live-first auto mode and synthetic fallback."""

    _STEP_MINUTES = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }

    _YF_INTERVAL = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "60m",
        "4h": "60m",
        "1d": "1d",
    }

    @staticmethod
    def _symbol_to_yahoo(symbol: str) -> str:
        s = symbol.strip().upper()
        index_map = {
            "NIFTY": "^NSEI",
            "NIFTY50": "^NSEI",
            "BANKNIFTY": "^NSEBANK",
            "SENSEX": "^BSESN",
            "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
        }
        if s in index_map:
            return index_map[s]
        if s.startswith("^") or s.endswith(".NS") or s.endswith(".BO"):
            return s
        if "NIFTY" in s and "BANK" in s:
            return "^NSEBANK"
        if "NIFTY" in s:
            return "^NSEI"
        if "SENSEX" in s:
            return "^BSESN"
        return f"{s}.NS"

    def _build_period(self, timeframe: str, limit: int) -> str:
        step_minutes = self._STEP_MINUTES.get(timeframe, 15)
        total_minutes = max(1, step_minutes * max(1, limit))
        if step_minutes < 1440:
            # Intraday data on Yahoo is capped (typically around 60 days).
            days = max(7, min(59, int(math.ceil(total_minutes / 1440.0)) + 5))
            return f"{days}d"
        days = max(90, int(math.ceil(total_minutes / 1440.0)) + 30)
        if days <= 365:
            return "1y"
        if days <= 365 * 2:
            return "2y"
        if days <= 365 * 5:
            return "5y"
        return "10y"

    def _resample_4h(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows
        grouped: list[dict[str, Any]] = []
        bucket: list[dict[str, Any]] = []
        for row in rows:
            bucket.append(row)
            if len(bucket) == 4:
                grouped.append(
                    {
                        "ts": bucket[-1]["ts"],
                        "open": bucket[0]["open"],
                        "high": max(x["high"] for x in bucket),
                        "low": min(x["low"] for x in bucket),
                        "close": bucket[-1]["close"],
                        "volume": sum(x["volume"] for x in bucket),
                    }
                )
                bucket = []
        if bucket:
            grouped.append(
                {
                    "ts": bucket[-1]["ts"],
                    "open": bucket[0]["open"],
                    "high": max(x["high"] for x in bucket),
                    "low": min(x["low"] for x in bucket),
                    "close": bucket[-1]["close"],
                    "volume": sum(x["volume"] for x in bucket),
                }
            )
        return grouped

    def _live_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        interval = self._YF_INTERVAL.get(timeframe, "15m")
        ticker = self._symbol_to_yahoo(symbol)
        period = self._build_period(timeframe, limit)
        try:
            import yfinance as yf  # type: ignore
        except Exception:
            return []

        try:
            frame = yf.download(
                tickers=ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=False,
                threads=False,
            )
        except Exception:
            return []

        if frame is None or frame.empty:
            return []

        # yfinance can return multi-index columns depending on version and arguments.
        if hasattr(frame.columns, "nlevels") and getattr(frame.columns, "nlevels", 1) > 1:
            frame.columns = frame.columns.get_level_values(0)

        cols = {str(c).lower(): c for c in frame.columns}
        required = ["open", "high", "low", "close"]
        if any(name not in cols for name in required):
            return []

        rows: list[dict[str, Any]] = []
        for idx, row in frame.iterrows():
            try:
                rows.append(
                    {
                        "ts": idx.to_pydatetime().astimezone(timezone.utc).isoformat(),
                        "open": float(row[cols["open"]]),
                        "high": float(row[cols["high"]]),
                        "low": float(row[cols["low"]]),
                        "close": float(row[cols["close"]]),
                        "volume": float(row[cols["volume"]]) if "volume" in cols else 0.0,
                    }
                )
            except Exception:
                continue

        if timeframe == "4h":
            rows = self._resample_4h(rows)

        rows = rows[-limit:]
        if len(rows) < max(80, min(120, limit // 2)):
            return []
        return [
            Candle(
                ts=r["ts"],
                open=round(r["open"], 2),
                high=round(r["high"], 2),
                low=round(r["low"], 2),
                close=round(r["close"], 2),
                volume=round(r["volume"], 2),
            )
            for r in rows
        ]

    def _synthetic_candles(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        seed = sum(ord(ch) for ch in f"{symbol}:{timeframe}")
        random.seed(seed)
        base = 100 + (seed % 500)
        now = datetime.now(timezone.utc)

        step_minutes = self._STEP_MINUTES.get(timeframe, 15)

        candles: list[Candle] = []
        price = float(base)
        for i in range(limit):
            ts = now - timedelta(minutes=(limit - i) * step_minutes)
            drift = random.uniform(-1.5, 1.5)
            vol = random.uniform(0.15, 2.0)
            open_p = price
            high_p = open_p + abs(drift) * random.uniform(0.4, 1.2)
            low_p = open_p - vol
            close_p = max(1.0, open_p + drift)
            volume = random.uniform(10_000, 450_000)
            price = close_p
            candles.append(
                Candle(
                    ts=ts.isoformat(),
                    open=round(open_p, 2),
                    high=round(max(high_p, close_p, open_p), 2),
                    low=round(min(low_p, close_p, open_p), 2),
                    close=round(close_p, 2),
                    volume=round(volume, 2),
                )
            )
        return candles

    def get_candles(self, symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        mode = get_settings().market_data_mode.lower().strip()
        if mode in {"auto", "live"}:
            live = self._live_candles(symbol, timeframe, limit)
            if live:
                return live
        return self._synthetic_candles(symbol, timeframe, limit)
