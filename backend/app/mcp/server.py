from __future__ import annotations

from app.mcp import tools

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit(
        "mcp package not installed. Install backend deps with `pip install -e .` first."
    ) from exc


mcp = FastMCP("multi-agent-trading-mcp")


@mcp.tool()
def analyze_symbol(symbol: str, segment: str = "equity", timeframe: str = "15m") -> dict:
    """Run multi-agent analysis for a symbol."""
    return tools.analyze_symbol(symbol=symbol, segment=segment, timeframe=timeframe)


@mcp.tool()
def backtest_symbol(symbol: str, strategy: str = "smc_breakout") -> dict:
    """Backtest strategy for a symbol."""
    return tools.backtest_symbol(symbol=symbol, strategy=strategy)


@mcp.tool()
def portfolio_snapshot(capital: float, holdings: list[dict]) -> dict:
    """Analyze portfolio metrics and concentration risk."""
    return tools.portfolio_snapshot(capital=capital, holdings=holdings)


@mcp.tool()
def place_paper_order(symbol: str, side: str, qty: int, segment: str = "equity") -> dict:
    """Route a paper trade through broker simulator."""
    return tools.place_paper_order(symbol=symbol, side=side, qty=qty, segment=segment)


if __name__ == "__main__":
    mcp.run()
