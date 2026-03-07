from __future__ import annotations

from app.models.analysis import Candle


def _swing_points(candles: list[Candle], lookback: int = 3) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []

    for i in range(lookback, len(candles) - lookback):
        window = candles[i - lookback : i + lookback + 1]
        center = candles[i]
        if center.high == max(c.high for c in window):
            highs.append((i, center.high))
        if center.low == min(c.low for c in window):
            lows.append((i, center.low))
    return highs, lows


def detect_market_structure(candles: list[Candle]) -> dict:
    if len(candles) < 20:
        return {
            "bos": "none",
            "choch": "none",
            "trend": "neutral",
            "liquidity_sweeps": [],
            "fvg_zones": [],
            "order_blocks": [],
            "support": [],
            "resistance": [],
            "premium_zone": None,
            "discount_zone": None,
        }

    swing_highs, swing_lows = _swing_points(candles)
    closes = [c.close for c in candles]

    trend = "neutral"
    if closes[-1] > closes[-20]:
        trend = "uptrend"
    elif closes[-1] < closes[-20]:
        trend = "downtrend"

    bos = "none"
    choch = "none"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        last_high = swing_highs[-1][1]
        prev_high = swing_highs[-2][1]
        last_low = swing_lows[-1][1]
        prev_low = swing_lows[-2][1]

        if last_high > prev_high and trend == "uptrend":
            bos = "bullish_bos"
        elif last_low < prev_low and trend == "downtrend":
            bos = "bearish_bos"

        if trend == "uptrend" and last_low < prev_low:
            choch = "bearish_choch"
        elif trend == "downtrend" and last_high > prev_high:
            choch = "bullish_choch"

    fvg_zones = []
    for i in range(2, len(candles)):
        c1 = candles[i - 2]
        c3 = candles[i]
        if c1.high < c3.low:
            fvg_zones.append({"type": "bullish_fvg", "low": c1.high, "high": c3.low, "index": i})
        elif c1.low > c3.high:
            fvg_zones.append({"type": "bearish_fvg", "low": c3.high, "high": c1.low, "index": i})

    order_blocks = []
    for i in range(1, len(candles) - 1):
        prev_c = candles[i - 1]
        curr = candles[i]
        nxt = candles[i + 1]
        if prev_c.close < prev_c.open and nxt.close > nxt.open and curr.low <= prev_c.low:
            order_blocks.append(
                {
                    "type": "bullish_ob",
                    "low": curr.low,
                    "high": curr.high,
                    "index": i,
                }
            )
        if prev_c.close > prev_c.open and nxt.close < nxt.open and curr.high >= prev_c.high:
            order_blocks.append(
                {
                    "type": "bearish_ob",
                    "low": curr.low,
                    "high": curr.high,
                    "index": i,
                }
            )

    liquidity_sweeps = []
    for i in range(2, len(candles)):
        left = candles[i - 2]
        mid = candles[i - 1]
        curr = candles[i]
        if curr.high > max(left.high, mid.high) and curr.close < curr.high:
            liquidity_sweeps.append({"type": "buy_side_sweep", "price": curr.high, "index": i})
        if curr.low < min(left.low, mid.low) and curr.close > curr.low:
            liquidity_sweeps.append({"type": "sell_side_sweep", "price": curr.low, "index": i})

    local_high = max(c.high for c in candles[-60:])
    local_low = min(c.low for c in candles[-60:])
    eq = (local_high + local_low) / 2

    support = sorted({round(l[1], 2) for l in swing_lows[-5:]})
    resistance = sorted({round(h[1], 2) for h in swing_highs[-5:]})

    return {
        "bos": bos,
        "choch": choch,
        "trend": trend,
        "liquidity_sweeps": liquidity_sweeps[-5:],
        "fvg_zones": fvg_zones[-8:],
        "order_blocks": order_blocks[-8:],
        "support": support,
        "resistance": resistance,
        "premium_zone": {"from": eq, "to": local_high},
        "discount_zone": {"from": local_low, "to": eq},
    }
