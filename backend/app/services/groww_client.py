from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

import httpx

from app.core.config import get_settings
from app.models.trading import OrderRequest


@dataclass
class GrowwBrokerClient:
    """Groww connector scaffold.

    Keep `mode=paper` by default until the exact broker API contract is verified.
    """

    def _auth_headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.groww_totp_token}",
            "X-TOTP-SECRET": settings.groww_totp_secret or "",
            "Content-Type": "application/json",
        }

    def _simulated_holdings(self) -> list[dict[str, Any]]:
        return [
            {"symbol": "RELIANCE", "qty": 8, "avg_price": 2460.0, "last_price": 2528.5},
            {"symbol": "ICICIBANK", "qty": 20, "avg_price": 1085.0, "last_price": 1121.4},
            {"symbol": "TCS", "qty": 5, "avg_price": 3920.0, "last_price": 4010.0},
            {"symbol": "HDFCBANK", "qty": 14, "avg_price": 1562.0, "last_price": 1611.3},
        ]

    def _extract_holdings(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = []
        for key in ("holdings", "data", "result", "positions"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                nested = value.get("holdings") or value.get("positions")
                if isinstance(nested, list):
                    candidates = nested
                    break

        parsed: list[dict[str, Any]] = []
        for item in candidates:
            symbol = item.get("symbol") or item.get("tradingSymbol") or item.get("securityName")
            qty = item.get("qty") or item.get("quantity")
            avg_price = item.get("avgPrice") or item.get("averagePrice") or item.get("buyPrice")
            last_price = item.get("ltp") or item.get("lastPrice") or item.get("closePrice")

            if not symbol or qty is None or avg_price is None or last_price is None:
                continue

            parsed.append(
                {
                    "symbol": str(symbol),
                    "qty": float(qty),
                    "avg_price": float(avg_price),
                    "last_price": float(last_price),
                }
            )
        return parsed

    async def fetch_portfolio(self) -> dict[str, Any]:
        settings = get_settings()
        if not settings.groww_totp_token:
            simulated = self._simulated_holdings()
            return {
                "status": "fallback",
                "source": "simulated",
                "message": "Groww token missing; using simulated holdings.",
                "positions": simulated,
            }

        headers = self._auth_headers()
        endpoints = [
            "/v1/portfolio/holdings",
            "/v1/holdings",
            "/v1/portfolio",
        ]

        async with httpx.AsyncClient(timeout=12) as client:
            for ep in endpoints:
                try:
                    url = f"{settings.groww_api_base_url.rstrip('/')}{ep}"
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    payload = response.json()
                    positions = self._extract_holdings(payload)
                    if positions:
                        return {
                            "status": "synced",
                            "source": "groww",
                            "message": f"Portfolio synced from {ep}.",
                            "positions": positions,
                        }
                except Exception:
                    continue

        simulated = self._simulated_holdings()
        return {
            "status": "fallback",
            "source": "simulated",
            "message": "Groww portfolio endpoint unavailable; using simulated holdings.",
            "positions": simulated,
        }

    async def place_order(self, req: OrderRequest) -> dict:
        settings = get_settings()

        if req.mode == "paper":
            return {
                "order_id": f"paper-{uuid.uuid4().hex[:12]}",
                "status": "simulated",
                "mode": "paper",
                "message": "Paper trade filled in simulator.",
                "broker_payload": {
                    "symbol": req.symbol,
                    "side": req.side,
                    "qty": req.qty,
                    "order_type": req.order_type,
                    "segment": req.segment,
                },
            }

        headers = self._auth_headers()
        payload = {
            "symbol": req.symbol,
            "side": req.side.upper(),
            "quantity": req.qty,
            "orderType": req.order_type.upper(),
            "limitPrice": req.limit_price,
            "product": req.product_type.upper(),
            "segment": req.segment.upper(),
        }

        async with httpx.AsyncClient(timeout=12) as client:
            # Update endpoint according to Groww official API docs.
            url = f"{settings.groww_api_base_url.rstrip('/')}/v1/orders"
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        return {
            "order_id": data.get("orderId", f"live-{uuid.uuid4().hex[:12]}"),
            "status": "accepted",
            "mode": "live",
            "message": "Order routed to broker.",
            "broker_payload": data,
        }
