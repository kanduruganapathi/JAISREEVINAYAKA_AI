from __future__ import annotations

import logging

from app.core.config import get_settings


logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _is_configured(self) -> bool:
        return bool(
            self.settings.twilio_account_sid
            and self.settings.twilio_auth_token
            and self.settings.twilio_whatsapp_from
            and self.settings.whatsapp_to
        )

    def send_whatsapp(self, message: str) -> dict:
        if not self._is_configured():
            return {
                "status": "skipped",
                "message": "Twilio WhatsApp config missing. Alert not sent.",
            }

        from_number = self.settings.twilio_whatsapp_from.strip()
        to_number = (self.settings.whatsapp_to or "").strip()

        # Twilio rejects requests when sender and receiver are the same number.
        if from_number == to_number:
            return {
                "status": "skipped",
                "message": "Twilio requires different WhatsApp To and From numbers.",
            }

        from twilio.base.exceptions import TwilioRestException
        from twilio.rest import Client

        try:
            client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
            msg = client.messages.create(
                body=message,
                from_=from_number,
                to=to_number,
            )
            return {
                "status": "sent",
                "sid": msg.sid,
            }
        except TwilioRestException as exc:
            logger.warning("Twilio WhatsApp failed: code=%s msg=%s", exc.code, exc.msg)
            return {
                "status": "failed",
                "message": exc.msg or str(exc),
                "error_code": exc.code,
            }
        except Exception as exc:  # pragma: no cover - network/provider edge cases
            logger.warning("WhatsApp notification failed: %s", exc)
            return {
                "status": "failed",
                "message": str(exc),
            }
