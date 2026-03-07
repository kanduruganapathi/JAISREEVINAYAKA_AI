import { FormEvent, useMemo, useState } from "react";

import { api } from "./api/client";
import SectionCard from "./components/SectionCard";
import { AnalysisResponse, BacktestResponse, PortfolioResponse } from "./types";

const defaultPositions = JSON.stringify(
  [
    { symbol: "RELIANCE", qty: 10, avg_price: 2450, last_price: 2525 },
    { symbol: "TCS", qty: 5, avg_price: 3950, last_price: 4020 },
  ],
  null,
  2
);

export default function App() {
  const [health, setHealth] = useState("unknown");

  const [symbol, setSymbol] = useState("NIFTY");
  const [segment, setSegment] = useState("intraday_options");
  const [timeframe, setTimeframe] = useState("15m");
  const [notify, setNotify] = useState(true);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);

  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [strategy, setStrategy] = useState("smc_breakout");

  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [capital, setCapital] = useState(100000);
  const [positionsText, setPositionsText] = useState(defaultPositions);

  const [mode, setMode] = useState<"paper" | "live">("paper");
  const [orderMsg, setOrderMsg] = useState<string>("");
  const [qty, setQty] = useState(25);

  const [question, setQuestion] = useState("What is best risk plan for BankNifty intraday breakout today?");
  const [chatAnswer, setChatAnswer] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const biasTone = useMemo(() => {
    if (!analysis) return "tone-neutral";
    if (analysis.consensus_bias === "bullish") return "tone-bull";
    if (analysis.consensus_bias === "bearish") return "tone-bear";
    return "tone-neutral";
  }, [analysis]);

  const refreshHealth = async () => {
    try {
      const h = await api.health();
      setHealth(`${h.status} (${h.env})`);
    } catch {
      setHealth("down");
    }
  };

  const runAnalysis = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const payload = {
        symbol,
        segment,
        primary_timeframe: timeframe,
        secondary_timeframes: ["5m", "1h", "1d"],
        include_fundamental: true,
        include_technical: true,
        include_news: true,
        include_events: true,
        include_smc: true,
        include_price_action: true,
        include_indicators: true,
      };
      const result = (await api.runAnalysis(payload, notify)) as AnalysisResponse;
      setAnalysis(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const runBacktest = async () => {
    setError("");
    setLoading(true);
    try {
      const payload = {
        symbol,
        segment,
        candles: [],
        initial_capital: capital,
        commission_per_trade: 20,
        slippage_bps: 5,
        rule: { name: strategy, params: {} },
      };
      // backend uses supplied candles; for demo we reuse analysis request style by fetching generated set via MCP/backtest endpoint logic
      const result = (await api.runBacktest(payload)) as BacktestResponse;
      setBacktest(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const runPortfolio = async () => {
    setError("");
    setLoading(true);
    try {
      const positions = JSON.parse(positionsText);
      const payload = { capital, positions };
      const result = (await api.analyzePortfolio(payload)) as PortfolioResponse;
      setPortfolio(result);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const placeOrder = async () => {
    setError("");
    setLoading(true);
    try {
      const payload = {
        symbol,
        segment: segment.includes("option") ? "index_option" : "equity",
        side: analysis?.trade_plan.action === "sell" ? "sell" : "buy",
        qty,
        order_type: "market",
        product_type: "intraday",
        mode,
      };
      const result = (await api.placeOrder(payload)) as {
        status: string;
        order_id: string;
        message: string;
      };
      setOrderMsg(`${result.status}: ${result.order_id} - ${result.message}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const askChat = async () => {
    setError("");
    setLoading(true);
    try {
      const result = (await api.askChat({
        question,
        context: {
          symbol,
          segment,
          timeframe,
          current_bias: analysis?.consensus_bias,
          trade_plan: analysis?.trade_plan,
        },
      })) as { answer: string };
      setChatAnswer(result.answer);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <div className="ambient one" />
      <div className="ambient two" />
      <header className="hero">
        <div>
          <h1>Multi-Agent Trading Command Center</h1>
          <p>SMC + Price Action + Fundamentals + News + Events + Risk + Execution</p>
        </div>
        <div className="hero-actions">
          <button onClick={refreshHealth}>Backend Health</button>
          <span className="pill">{health}</span>
        </div>
      </header>

      <main className="grid">
        <SectionCard title="Market Analysis" subtitle="Multi-timeframe + smart-money confluence">
          <form className="form-grid" onSubmit={runAnalysis}>
            <label>
              Symbol
              <input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </label>
            <label>
              Segment
              <select value={segment} onChange={(e) => setSegment(e.target.value)}>
                <option value="intraday_options">Intraday Index Options</option>
                <option value="stock_options">Stock Options</option>
                <option value="equity">Equity</option>
                <option value="swing_stock">Swing Stock</option>
              </select>
            </label>
            <label>
              Timeframe
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
                <option>5m</option>
                <option>15m</option>
                <option>1h</option>
                <option>1d</option>
              </select>
            </label>
            <label className="inline">
              <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
              WhatsApp alerts
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "Running..." : "Run Analysis"}
            </button>
          </form>

          {analysis ? (
            <div className={`result ${biasTone}`}>
              <h3>
                {analysis.symbol} | {analysis.consensus_bias.toUpperCase()} | Score {analysis.score}
              </h3>
              <p>{analysis.trade_plan.rationale}</p>
              <p>
                Action: <strong>{analysis.trade_plan.action.toUpperCase()}</strong> | Entry: {analysis.trade_plan.entry ?? "-"} |
                Stop: {analysis.trade_plan.stop_loss ?? "-"} | Target: {analysis.trade_plan.target ?? "-"}
              </p>
              <p>
                Max Position Size: {analysis.risk.max_position_size} | RR: {analysis.risk.risk_reward_ratio}
              </p>
              <div className="agent-grid">
                {analysis.signals.map((s) => (
                  <article key={s.agent} className="agent">
                    <strong>{s.agent}</strong>
                    <span>{s.bias}</span>
                    <span>{s.confidence}</span>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Strategy Lab" subtitle="Backtesting and walk-forward validation">
          <div className="form-grid">
            <label>
              Strategy
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                <option value="smc_breakout">SMC Breakout</option>
                <option value="ema_cross">EMA Cross</option>
                <option value="rsi_reversion">RSI Reversion</option>
                <option value="multi_timeframe_breakout">MTF Breakout</option>
              </select>
            </label>
            <label>
              Capital
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value || 0))}
              />
            </label>
            <button onClick={runBacktest} disabled={loading}>
              Run Backtest
            </button>
          </div>
          {backtest ? (
            <div className="result">
              <p>Total Return: {backtest.total_return_pct}%</p>
              <p>Win Rate: {backtest.win_rate_pct}%</p>
              <p>Max Drawdown: {backtest.max_drawdown_pct}%</p>
              <p>Sharpe: {backtest.sharpe}</p>
              <p>Trades: {backtest.trades.length}</p>
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Portfolio Analytics" subtitle="PnL, concentration risk, VaR">
          <div className="form-grid">
            <label>
              Portfolio Capital
              <input
                type="number"
                value={capital}
                onChange={(e) => setCapital(Number(e.target.value || 0))}
              />
            </label>
            <label>
              Positions JSON
              <textarea value={positionsText} onChange={(e) => setPositionsText(e.target.value)} rows={8} />
            </label>
            <button onClick={runPortfolio} disabled={loading}>
              Analyze Portfolio
            </button>
          </div>
          {portfolio ? (
            <div className="result">
              <p>Total Value: {portfolio.total_value}</p>
              <p>Total PnL: {portfolio.total_pnl} ({portfolio.total_pnl_pct}%)</p>
              <p>Concentration Risk: {portfolio.concentration_risk_pct}%</p>
              <p>VaR 95: {portfolio.value_at_risk_95}</p>
              {portfolio.recommendations.map((r) => (
                <p key={r}>- {r}</p>
              ))}
            </div>
          ) : null}
        </SectionCard>

        <SectionCard title="Execution Desk" subtitle="Paper and live mode are isolated">
          <div className="form-grid">
            <div className="mode-toggle">
              <button
                className={mode === "paper" ? "active" : ""}
                onClick={() => setMode("paper")}
                type="button"
              >
                Paper
              </button>
              <button
                className={mode === "live" ? "active" : ""}
                onClick={() => setMode("live")}
                type="button"
              >
                Live
              </button>
            </div>
            <label>
              Quantity
              <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value || 1))} />
            </label>
            <button onClick={placeOrder} disabled={loading}>
              Place Order
            </button>
          </div>
          {orderMsg ? <div className="result"><p>{orderMsg}</p></div> : null}
        </SectionCard>

        <SectionCard title="Market Intelligence Chat" subtitle="Q&A for setup quality, risk, and scenario planning">
          <div className="form-grid">
            <label>
              Question
              <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={4} />
            </label>
            <button onClick={askChat} disabled={loading}>
              Ask
            </button>
          </div>
          {chatAnswer ? <div className="result"><p>{chatAnswer}</p></div> : null}
        </SectionCard>
      </main>

      {error ? <aside className="error">{error}</aside> : null}
    </div>
  );
}
