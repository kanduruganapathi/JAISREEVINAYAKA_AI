# Multi-Agent Trading Intelligence Platform

Full-stack trading research and execution platform with:

- FastAPI backend
- React + TypeScript frontend
- Multi-agent analysis (fundamental, technical, news, events, SMC, risk)
- Strategy lab (backtest + walk-forward simulation)
- Portfolio analytics
- Paper and live order routing (separate)
- MCP server and MCP tools
- WhatsApp alerts (Twilio)
- Groww broker connector scaffold

## Security First

You shared real-looking credentials in chat. Assume they are compromised and rotate them immediately:

- Groww token and secret
- TimescaleDB password
- Gemini API key
- Twilio SID/Auth token

Never commit `.env` to git.

## Monorepo Layout

- `backend/` FastAPI app + agents + MCP
- `frontend/` React dashboard

## Quick Start

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend expects backend at `http://localhost:8000`.

## API Overview

- `POST /api/v1/analysis/run`
- `POST /api/v1/backtest/run`
- `POST /api/v1/trading/order`
- `POST /api/v1/portfolio/analyze`
- `POST /api/v1/chat/query`
- `POST /api/v1/notifications/whatsapp/test`

## MCP

Run MCP server:

```bash
cd backend
python -m app.mcp.server
```

## Notes

This implementation gives production-grade architecture and working baseline logic. For real-money deployment, add:

- Exchange-grade risk limits
- Real-time websocket feeds
- Full broker API contract validation
- Compliance logging and auditing
- Secrets manager integration
