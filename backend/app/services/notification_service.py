from __future__ import annotations

from app.core.config import get_settings


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

        from twilio.rest import Client

        client = Client(self.settings.twilio_account_sid, self.settings.twilio_auth_token)
        msg = client.messages.create(
            body=message,
            from_=self.settings.twilio_whatsapp_from,
            to=self.settings.whatsapp_to,
        )
        return {
            "status": "sent",
            "sid": msg.sid,
        }
