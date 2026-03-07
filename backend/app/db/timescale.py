from __future__ import annotations

from sqlalchemy import create_engine

from app.core.config import get_settings


def build_db_url() -> str | None:
    s = get_settings()
    if not (s.db_username and s.db_password and s.db_host):
        return None
    return f"postgresql+psycopg2://{s.db_username}:{s.db_password}@{s.db_host}:{s.db_port}/{s.db_name}"


def create_timescale_engine():
    url = build_db_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)
