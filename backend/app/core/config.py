from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", alias="APP_ENV")
    app_name: str = Field(default="Multi-Agent Trading Platform", alias="APP_NAME")
    api_port: int = Field(default=8000, alias="API_PORT")
    frontend_origin: str = Field(default="http://localhost:5173", alias="FRONTEND_ORIGIN")

    groww_api_base_url: str = Field(default="https://api.groww.in", alias="GROWW_API_BASE_URL")
    groww_totp_token: str | None = Field(default=None, alias="GROWW_TOTP_TOKEN")
    groww_totp_secret: str | None = Field(default=None, alias="GROWW_TOTP_SECRET")

    db_username: str | None = Field(default=None, alias="DB_USERNAME")
    db_password: str | None = Field(default=None, alias="DB_PASSWORD")
    db_name: str = Field(default="tsdb", alias="DB_NAME")
    db_host: str | None = Field(default=None, alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")

    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")

    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str = Field(default="whatsapp:+14155238886", alias="TWILIO_WHATSAPP_FROM")
    whatsapp_to: str | None = Field(default=None, alias="WHATSAPP_TO")

    autonomous_enabled: bool = Field(default=False, alias="AUTONOMOUS_ENABLED")
    autonomous_max_capital: float = Field(default=50000.0, alias="AUTONOMOUS_MAX_CAPITAL")
    autonomous_paper_mode: bool = Field(default=True, alias="AUTONOMOUS_PAPER_MODE")
    live_trading_enabled: bool = Field(default=False, alias="LIVE_TRADING_ENABLED")
    max_order_notional: float = Field(default=10000.0, alias="MAX_ORDER_NOTIONAL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
