from __future__ import annotations

from dataclasses import dataclass
import uuid

import httpx

from app.core.config import get_settings
from app.models.trading import OrderRequest


@dataclass
class GrowwBrokerClient:
    """Groww connector scaffold.

    Keep `mode=paper` by default until the exact broker API contract is verified.
    """

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

        headers = {
            "Authorization": f"Bearer {settings.groww_totp_token}",
            "X-TOTP-SECRET": settings.groww_totp_secret or "",
            "Content-Type": "application/json",
        }
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
