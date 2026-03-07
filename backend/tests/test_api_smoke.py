from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_analysis() -> None:
    payload = {
        "symbol": "NIFTY",
        "segment": "intraday_options",
        "primary_timeframe": "15m",
        "secondary_timeframes": ["5m", "1h"],
    }
    res = client.post("/api/v1/analysis/run", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["symbol"] == "NIFTY"
    assert "trade_plan" in body


def test_backtest() -> None:
    payload = {
        "symbol": "BANKNIFTY",
        "segment": "intraday_options",
        "candles": [],
        "rule": {"name": "smc_breakout", "params": {}},
    }
    res = client.post("/api/v1/backtest/run", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "total_return_pct" in body


def test_scanner() -> None:
    payload = {"universe": "nifty50", "timeframe": "15m", "top_n": 5}
    res = client.post("/api/v1/scanner/run", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["scanned"] >= 5
    assert len(body["results"]) == 5


def test_groww_portfolio_sync() -> None:
    res = client.post("/api/v1/portfolio/groww/sync")
    assert res.status_code == 200
    body = res.json()
    assert "sync" in body
    assert "analysis" in body
