from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random

from app.models.analysis import Candle


@dataclass
class DataProvider:
    """Demo data provider.

    Replace this with real market feed integration (Groww websocket or vendor API).
    """

    def get_candles(self, symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        seed = sum(ord(ch) for ch in f"{symbol}:{timeframe}")
        random.seed(seed)
        base = 100 + (seed % 500)
        now = datetime.now(timezone.utc)

        step_minutes = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,
        }.get(timeframe, 15)

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
