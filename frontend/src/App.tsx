import { FormEvent, useMemo, useState } from "react";

import { api } from "./api/client";
import {
  AnalysisResponse,
  BacktestResponse,
  GrowwPortfolioSyncResponse,
  PortfolioResponse,
  StockScanResponse,
} from "./types";

type ViewKey =
  | "dashboard"
  | "scanner"
  | "options"
  | "strategy"
  | "portfolio"
  | "execution"
  | "chat";

const VIEW_ITEMS: Array<{ key: ViewKey; label: string; hint: string }> = [
  { key: "dashboard", label: "Trading Dashboard", hint: "Multi-agent decision and confluence" },
  { key: "scanner", label: "Nifty 50 Scanner", hint: "News + Fundamental + Breakout + Technical" },
  { key: "options", label: "Options Desk", hint: "Intraday index/stock options playbooks" },
  { key: "strategy", label: "Strategy Lab", hint: "Backtest, validation, expectancy" },
  { key: "portfolio", label: "Portfolio", hint: "Groww sync + risk analytics" },
  { key: "execution", label: "Execution", hint: "Paper/live order controls" },
  { key: "chat", label: "Market Intel", hint: "Scenario Q&A and market intelligence" },
];

const defaultPositions = JSON.stringify(
  [
    { symbol: "RELIANCE", qty: 10, avg_price: 2450, last_price: 2525 },
    { symbol: "TCS", qty: 5, avg_price: 3950, last_price: 4020 },
  ],
  null,
  2
);

function fmt(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

function biasClass(bias: string): string {
  const normalized = bias.toLowerCase();
  if (["bullish", "long", "positive", "uptrend"].some((token) => normalized.includes(token))) {
    return "bias-bull";
  }
  if (["bearish", "short", "negative", "downtrend"].some((token) => normalized.includes(token))) {
    return "bias-bear";
  }
  return "bias-neutral";
}

function scoreBand(score: number): string {
  if (score >= 0.78) return "A+";
  if (score >= 0.68) return "A";
  if (score >= 0.58) return "B";
  if (score >= 0.5) return "C";
  return "D";
}

export default function App() {
  const [view, setView] = useState<ViewKey>("dashboard");
  const [health, setHealth] = useState("unknown");

  const [symbol, setSymbol] = useState("NIFTY");
  const [segment, setSegment] = useState("intraday_options");
  const [timeframe, setTimeframe] = useState("15m");
  const [notify, setNotify] = useState(true);

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [backtest, setBacktest] = useState<BacktestResponse | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [scanner, setScanner] = useState<StockScanResponse | null>(null);
  const [growwSync, setGrowwSync] = useState<GrowwPortfolioSyncResponse | null>(null);

  const [strategy, setStrategy] = useState("smc_breakout");
  const [capital, setCapital] = useState(100000);
  const [positionsText, setPositionsText] = useState(defaultPositions);

  const [mode, setMode] = useState<"paper" | "live">("paper");
  const [qty, setQty] = useState(25);
  const [orderMsg, setOrderMsg] = useState("");

  const [question, setQuestion] = useState(
    "Give me intraday BankNifty options plan with entry, stop, target and invalidation."
  );
  const [chatAnswer, setChatAnswer] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const overallTone = useMemo(() => {
    if (!analysis) return "bias-neutral";
    return biasClass(analysis.consensus_bias);
  }, [analysis]);

  const optionsIdeas = useMemo(
    () =>
      analysis?.strategy_ideas.filter(
        (x) =>
          x.instrument.toLowerCase().includes("ce") ||
          x.instrument.toLowerCase().includes("pe") ||
          x.instrument.toLowerCase().includes("spread") ||
          x.instrument.toLowerCase().includes("straddle")
      ) ?? [],
    [analysis]
  );

  const liveNews = useMemo(() => {
    const empty = {
      headlines: [] as string[],
      source: "-",
      mode: "-",
      timestamp: "-",
      sentiment: "neutral",
      score: 0.5,
    };
    if (!analysis) return empty;
    const signal = analysis.signals.find((x) => x.agent === "news_analyst");
    if (!signal) return empty;

    const details = signal.details as Record<string, unknown>;
    const headlines = Array.isArray(details.headlines) ? details.headlines.map((x) => String(x)) : [];
    return {
      headlines,
      source: String(details.source ?? "-"),
      mode: String(details.mode ?? "-"),
      timestamp: String(details.timestamp ?? "-"),
      sentiment: String(details.sentiment ?? "neutral"),
      score: Number(details.score ?? signal.confidence ?? 0.5),
    };
  }, [analysis]);

  const dashboardKpis = useMemo(
    () => [
      {
        label: "Setup Edge",
        value: analysis ? `${Math.round(analysis.score * 100)}%` : "--",
        tone: analysis ? biasClass(analysis.consensus_bias) : "bias-neutral",
      },
      {
        label: "Execution Bias",
        value: analysis?.trade_plan.action.toUpperCase() ?? "WAIT",
        tone: analysis ? biasClass(analysis.trade_plan.action) : "bias-neutral",
      },
      {
        label: "Live News",
        value: `${liveNews.sentiment.toUpperCase()} ${Math.round(liveNews.score * 100)}%`,
        tone: biasClass(liveNews.sentiment),
      },
      {
        label: "Scanner HC",
        value: scanner ? `${scanner.summary.high_confidence}/${scanner.summary.scanned}` : "--",
        tone: scanner
          ? scanner.summary.bullish >= scanner.summary.bearish
            ? "bias-bull"
            : "bias-bear"
          : "bias-neutral",
      },
      {
        label: "Portfolio Risk",
        value: portfolio ? `${fmt(portfolio.concentration_risk_pct)}%` : "--",
        tone:
          portfolio && portfolio.concentration_risk_pct > 45
            ? "bias-bear"
            : portfolio
              ? "bias-neutral"
              : "bias-neutral",
      },
      {
        label: "Runtime",
        value: `${segment.replace(/_/g, " ")} • ${timeframe}`,
        tone: "bias-neutral",
      },
    ],
    [analysis, liveNews, portfolio, scanner, segment, timeframe]
  );

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
      const result = (await api.runAnalysis(
        {
          symbol,
          segment,
          primary_timeframe: timeframe,
          secondary_timeframes: ["5m", "15m", "1h", "1d"],
          include_fundamental: true,
          include_technical: true,
          include_news: true,
          include_events: true,
          include_smc: true,
          include_price_action: true,
          include_indicators: true,
        },
        notify
      )) as AnalysisResponse;
      setAnalysis(result);
      setOrderMsg("");
      if (view === "scanner") {
        setView("dashboard");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const runScanner = async () => {
    setError("");
    setLoading(true);
    try {
      const result = (await api.runScanner({
        universe: "nifty50",
        timeframe: "15m",
        top_n: 15,
        include_news: true,
        include_fundamental: true,
        include_breakout: true,
        include_technical: true,
      })) as StockScanResponse;
      setScanner(result);
      setView("scanner");
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
      const result = (await api.runBacktest({
        symbol,
        segment,
        candles: [],
        initial_capital: capital,
        commission_per_trade: 20,
        slippage_bps: 5,
        rule: { name: strategy, params: {} },
      })) as BacktestResponse;
      setBacktest(result);
      setView("strategy");
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
      const result = (await api.analyzePortfolio({ capital, positions })) as PortfolioResponse;
      setPortfolio(result);
      setView("portfolio");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const syncGrowwPortfolio = async () => {
    setError("");
    setLoading(true);
    try {
      const syncResult = (await api.syncGrowwPortfolio()) as GrowwPortfolioSyncResponse;
      setGrowwSync(syncResult);
      setPortfolio(syncResult.analysis);
      setCapital(syncResult.analysis.total_value || capital);
      setPositionsText(JSON.stringify(syncResult.positions, null, 2));
      setView("portfolio");
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
      const result = (await api.placeOrder({
        symbol,
        segment: segment.includes("option") ? "index_option" : "equity",
        side: analysis?.trade_plan.action === "sell" ? "sell" : "buy",
        qty,
        order_type: "market",
        product_type: "intraday",
        mode,
      })) as { status: string; order_id: string; message: string };
      setOrderMsg(`${result.status.toUpperCase()} | ${result.order_id} | ${result.message}`);
      setView("execution");
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
          trade_plan: analysis?.trade_plan,
          checklist: analysis?.execution_checklist,
          scanner_top: scanner?.results.slice(0, 5),
          strategy_ideas: analysis?.strategy_ideas,
        },
      })) as { answer: string };
      setChatAnswer(result.answer);
      setView("chat");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const renderDashboard = () => {
    if (!analysis) {
      return (
        <section className="panel panel-wide">
          <h2>Run Multi-Agent Analysis</h2>
          <p>
            Configure symbol, segment and timeframe, then execute analysis to generate trading plan,
            market-structure map, and strategy playbook.
          </p>
        </section>
      );
    }

    const structure = analysis.market_structure;

    return (
      <>
        <section className={`panel panel-wide ${overallTone}`}>
          <div className="panel-topline">
            <h2>
              {analysis.symbol} • {analysis.segment.replace(/_/g, " ")}
            </h2>
            <span className="grade-chip">Setup Grade {scoreBand(analysis.score)}</span>
          </div>
          <div className="headline-grid">
            <article>
              <label>Consensus</label>
              <p className="big">{analysis.consensus_bias.toUpperCase()}</p>
            </article>
            <article>
              <label>Action</label>
              <p className="big">{analysis.trade_plan.action.toUpperCase()}</p>
            </article>
            <article>
              <label>Entry / Stop / Target</label>
              <p>
                {fmt(analysis.trade_plan.entry)} / {fmt(analysis.trade_plan.stop_loss)} / {fmt(analysis.trade_plan.target)}
              </p>
            </article>
            <article>
              <label>Risk Reward</label>
              <p>{fmt(analysis.risk.risk_reward_ratio)}</p>
            </article>
          </div>
          <div className="confidence-wrap">
            <span>Confidence {Math.round(analysis.score * 100)}%</span>
            <div className="meter">
              <div className="meter-fill" style={{ width: `${Math.round(analysis.score * 100)}%` }} />
            </div>
          </div>
          <p className="muted">{analysis.trade_plan.rationale}</p>
        </section>

        <section className="panel">
          <h3>Indicator Snapshot</h3>
          <div className="kv-grid">
            <div>
              <span>EMA20</span>
              <strong>{fmt(analysis.indicator_snapshot.ema_20)}</strong>
            </div>
            <div>
              <span>EMA50</span>
              <strong>{fmt(analysis.indicator_snapshot.ema_50)}</strong>
            </div>
            <div>
              <span>RSI14</span>
              <strong>{fmt(analysis.indicator_snapshot.rsi_14)}</strong>
            </div>
            <div>
              <span>MACD Hist</span>
              <strong>{fmt(analysis.indicator_snapshot.histogram, 4)}</strong>
            </div>
            <div>
              <span>ATR14</span>
              <strong>{fmt(analysis.indicator_snapshot.atr_14)}</strong>
            </div>
            <div>
              <span>Volatility</span>
              <strong>{fmt(analysis.indicator_snapshot.volatility, 4)}</strong>
            </div>
          </div>
        </section>

        <section className="panel">
          <h3>Multi-Timeframe Matrix</h3>
          <div className="matrix">
            {analysis.timeframe_biases.map((tf) => (
              <article key={tf.timeframe} className={`matrix-row ${biasClass(tf.bias)}`}>
                <strong>{tf.timeframe}</strong>
                <span>{tf.bias.toUpperCase()}</span>
                <span>{Math.round(tf.confidence * 100)}%</span>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h3>Market Structure (SMC)</h3>
          {structure ? (
            <>
              <div className="kv-grid">
                <div>
                  <span>Trend</span>
                  <strong>{structure.trend}</strong>
                </div>
                <div>
                  <span>BOS</span>
                  <strong>{structure.bos}</strong>
                </div>
                <div>
                  <span>CHOCH</span>
                  <strong>{structure.choch}</strong>
                </div>
                <div>
                  <span>Liquidity Sweeps</span>
                  <strong>{structure.liquidity_sweeps.length}</strong>
                </div>
              </div>
              <p className="muted">Support: {structure.support.map((x) => fmt(x)).join(", ") || "-"}</p>
              <p className="muted">
                Resistance: {structure.resistance.map((x) => fmt(x)).join(", ") || "-"}
              </p>
            </>
          ) : (
            <p>No structure snapshot available.</p>
          )}
        </section>

        <section className="panel">
          <div className="panel-topline">
            <h3>Live News Pulse</h3>
            <span className={`live-pill ${biasClass(liveNews.sentiment)}`}>
              {liveNews.sentiment.toUpperCase()} {Math.round(liveNews.score * 100)}%
            </span>
          </div>
          <p className="muted">
            Source: {liveNews.source} • Mode: {liveNews.mode} • Updated: {liveNews.timestamp}
          </p>
          <ul className="checklist">
            {liveNews.headlines.slice(0, 4).map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
          {!liveNews.headlines.length ? <p className="muted">No live headlines available for this symbol right now.</p> : null}
        </section>

        <section className="panel panel-wide">
          <h3>Strategy Ideas</h3>
          <div className="ideas-grid">
            {analysis.strategy_ideas.map((idea) => (
              <article key={idea.name} className={`idea-card ${biasClass(idea.direction)}`}>
                <header>
                  <strong>{idea.name}</strong>
                  <span>{Math.round(idea.confidence * 100)}%</span>
                </header>
                <p className="muted">{idea.instrument}</p>
                <p>{idea.setup}</p>
                <p>
                  <b>Entry:</b> {idea.entry_trigger}
                </p>
                <p>
                  <b>Stop:</b> {idea.stop_rule}
                </p>
                <p>
                  <b>Targets:</b> {idea.targets.join(" | ")}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="panel panel-wide">
          <h3>Execution Checklist</h3>
          <ul className="checklist">
            {analysis.execution_checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          {!!analysis.risk.warnings.length && (
            <div className="warn-box">
              {analysis.risk.warnings.map((warn) => (
                <p key={warn}>{warn}</p>
              ))}
            </div>
          )}
        </section>
      </>
    );
  };

  const renderScanner = () => {
    return (
      <>
        <section className="panel panel-wide">
          <div className="row-head">
            <div>
              <h2>Nifty 50 Intraday Scanner</h2>
              <p>
                One-click scan for breakout candidates combining news flow, fundamentals, technical structure and intraday setup.
              </p>
            </div>
            <button onClick={runScanner} disabled={loading}>
              {loading ? "Scanning..." : "Run Nifty 50 Scan"}
            </button>
          </div>
        </section>

        {scanner ? (
          <>
            <section className="panel panel-wide">
              <h3>Scan Summary</h3>
              <div className="headline-grid">
                <article>
                  <label>Scanned</label>
                  <p className="big">{scanner.summary.scanned}</p>
                </article>
                <article className="bias-bull">
                  <label>Bullish</label>
                  <p className="big">{scanner.summary.bullish}</p>
                </article>
                <article className="bias-bear">
                  <label>Bearish</label>
                  <p className="big">{scanner.summary.bearish}</p>
                </article>
                <article>
                  <label>High Confidence</label>
                  <p className="big">{scanner.summary.high_confidence}</p>
                </article>
              </div>
            </section>

            <section className="panel panel-wide">
              <h3>Top Intraday Opportunities</h3>
              <div className="scanner-grid">
                {scanner.results.slice(0, 8).map((item) => (
                  <article key={item.symbol} className={`idea-card ${biasClass(item.bias)}`}>
                    <header>
                      <strong>
                        #{item.rank} {item.symbol}
                      </strong>
                      <span>{Math.round(item.overall_score * 100)}%</span>
                    </header>
                    <p className="muted">Action: {item.action.toUpperCase()} • Bias: {item.bias.toUpperCase()}</p>
                    <p className="muted">
                      News Mode: {item.news.meta?.mode ?? "-"} • Source: {item.news.meta?.source ?? "-"}
                    </p>
                    <p>
                      <b>News:</b> {item.news.summary || "No headline summary"}
                    </p>
                    <p>
                      <b>Setup:</b> {item.intraday_plan.setup}
                    </p>
                    <p>
                      <b>Entry:</b> {item.intraday_plan.entry_zone}
                    </p>
                    <p>
                      <b>Stop:</b> {item.intraday_plan.stop_loss}
                    </p>
                    <p>
                      <b>Targets:</b> {item.intraday_plan.targets.join(" | ")}
                    </p>
                    <p>
                      <b>RR Est:</b> {fmt(item.intraday_plan.rr_estimate)}
                    </p>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel panel-wide">
              <h3>Detailed Factor Table</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Symbol</th>
                      <th>Overall</th>
                      <th>News</th>
                      <th>News Mode</th>
                      <th>Fundamental</th>
                      <th>Breakout</th>
                      <th>Technical</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scanner.results.map((item) => (
                      <tr key={item.symbol}>
                        <td>{item.rank}</td>
                        <td>{item.symbol}</td>
                        <td>{Math.round(item.overall_score * 100)}%</td>
                        <td>{Math.round(item.news.score * 100)}%</td>
                        <td>{item.news.meta?.mode ?? "-"}</td>
                        <td>{Math.round(item.fundamental.score * 100)}%</td>
                        <td>{Math.round(item.breakout.score * 100)}%</td>
                        <td>{Math.round(item.technical.score * 100)}%</td>
                        <td>{item.action.toUpperCase()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : null}
      </>
    );
  };

  const renderOptionsDesk = () => {
    return (
      <>
        <section className="panel panel-wide">
          <h2>Intraday Options Playbook</h2>
          <p>
            Focus: NIFTY, BANKNIFTY, SENSEX with structure-confirmed entries, strict invalidation and fast risk-off exits.
          </p>
          <div className="playbook-grid">
            <article>
              <h4>Session Protocol</h4>
              <p>1) First 5 minutes no trade.</p>
              <p>2) Trade only BOS + pullback + displacement.</p>
              <p>3) Avoid new entries in final 20 minutes.</p>
            </article>
            <article>
              <h4>Risk Controls</h4>
              <p>Risk per trade &lt;= 1% capital.</p>
              <p>Premium stop 20-25% max.</p>
              <p>No revenge or averaging down.</p>
            </article>
            <article>
              <h4>Confluence Rules</h4>
              <p>15m structure + 5m execution must align.</p>
              <p>Liquidity sweep + FVG reaction preferred.</p>
              <p>Only trade liquid strikes.</p>
            </article>
          </div>
        </section>

        <section className="panel panel-wide">
          <h3>Current Option Strategy Setups</h3>
          {!analysis ? <p>Run analysis first.</p> : null}
          {!!analysis && !optionsIdeas.length ? <p>No options-specific setup. Stay selective.</p> : null}
          <div className="ideas-grid">
            {optionsIdeas.map((idea) => (
              <article key={idea.name} className={`idea-card ${biasClass(idea.direction)}`}>
                <header>
                  <strong>{idea.name}</strong>
                  <span>{idea.timeframe}</span>
                </header>
                <p>{idea.instrument}</p>
                <p>
                  <b>Entry:</b> {idea.entry_trigger}
                </p>
                <p>
                  <b>Stop:</b> {idea.stop_rule}
                </p>
                <p>
                  <b>Targets:</b> {idea.targets.join(" | ")}</p>
              </article>
            ))}
          </div>
        </section>
      </>
    );
  };

  const renderStrategyLab = () => {
    return (
      <>
        <section className="panel panel-wide">
          <h2>Strategy Lab</h2>
          <div className="controls-grid">
            <label>
              Rule
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
                <option value="smc_breakout">SMC Breakout</option>
                <option value="ema_cross">EMA Cross</option>
                <option value="rsi_reversion">RSI Reversion</option>
                <option value="multi_timeframe_breakout">MTF Breakout</option>
              </select>
            </label>
            <label>
              Initial Capital
              <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value || 0))} />
            </label>
            <button onClick={runBacktest} disabled={loading}>
              {loading ? "Running..." : "Run Backtest"}
            </button>
          </div>
        </section>

        {backtest && (
          <section className="panel panel-wide">
            <h3>Backtest Result</h3>
            <div className="kv-grid">
              <div>
                <span>Total Return</span>
                <strong>{fmt(backtest.total_return_pct)}%</strong>
              </div>
              <div>
                <span>Win Rate</span>
                <strong>{fmt(backtest.win_rate_pct)}%</strong>
              </div>
              <div>
                <span>Max Drawdown</span>
                <strong>{fmt(backtest.max_drawdown_pct)}%</strong>
              </div>
              <div>
                <span>Sharpe</span>
                <strong>{fmt(backtest.sharpe)}</strong>
              </div>
            </div>
            <h4>Recent Trades</h4>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>PnL</th>
                    <th>PnL%</th>
                  </tr>
                </thead>
                <tbody>
                  {backtest.trades.slice(-8).map((t, idx) => (
                    <tr key={`${t.entry_ts}-${idx}`}>
                      <td>{t.side}</td>
                      <td>{fmt(t.entry)}</td>
                      <td>{fmt(t.exit)}</td>
                      <td>{fmt(t.pnl)}</td>
                      <td>{fmt(t.pnl_pct)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </>
    );
  };

  const renderPortfolio = () => (
    <>
      <section className="panel panel-wide">
        <div className="row-head">
          <div>
            <h2>Portfolio Risk Engine</h2>
            <p>Analyze local holdings or sync directly from Groww and compute concentration and VaR profile.</p>
          </div>
          <button onClick={syncGrowwPortfolio} disabled={loading}>
            {loading ? "Syncing..." : "Sync Groww Portfolio"}
          </button>
        </div>

        {growwSync ? (
          <p className="muted">
            Sync status: {growwSync.sync.status.toUpperCase()} • Source: {growwSync.sync.source} • {growwSync.sync.message}
          </p>
        ) : null}

        <div className="controls-grid">
          <label>
            Capital
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value || 0))} />
          </label>
          <label className="span-2">
            Positions JSON
            <textarea rows={8} value={positionsText} onChange={(e) => setPositionsText(e.target.value)} />
          </label>
          <button onClick={runPortfolio} disabled={loading}>
            Analyze Portfolio
          </button>
        </div>
      </section>

      {portfolio && (
        <section className="panel panel-wide">
          <h3>Portfolio Snapshot</h3>
          <div className="kv-grid">
            <div>
              <span>Total Value</span>
              <strong>{fmt(portfolio.total_value)}</strong>
            </div>
            <div>
              <span>Total PnL</span>
              <strong>
                {fmt(portfolio.total_pnl)} ({fmt(portfolio.total_pnl_pct)}%)
              </strong>
            </div>
            <div>
              <span>Concentration Risk</span>
              <strong>{fmt(portfolio.concentration_risk_pct)}%</strong>
            </div>
            <div>
              <span>VaR 95</span>
              <strong>{fmt(portfolio.value_at_risk_95)}</strong>
            </div>
          </div>
          <ul className="checklist">
            {portfolio.recommendations.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );

  const renderExecution = () => (
    <>
      <section className="panel panel-wide">
        <h2>Execution Console</h2>
        <div className="controls-grid">
          <div className="toggle-row">
            <button className={mode === "paper" ? "active" : ""} onClick={() => setMode("paper")} type="button">
              Paper
            </button>
            <button className={mode === "live" ? "active" : ""} onClick={() => setMode("live")} type="button">
              Live
            </button>
          </div>
          <label>
            Quantity
            <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value || 1))} />
          </label>
          <label>
            Planned Side
            <input value={analysis?.trade_plan.action.toUpperCase() ?? "BUY"} readOnly />
          </label>
          <button onClick={placeOrder} disabled={loading}>
            Place Order
          </button>
        </div>
        {orderMsg ? <p className="muted">{orderMsg}</p> : null}
      </section>
    </>
  );

  const renderChat = () => (
    <>
      <section className="panel panel-wide">
        <h2>Market Intelligence Q&A</h2>
        <div className="controls-grid">
          <label className="span-2">
            Question
            <textarea rows={5} value={question} onChange={(e) => setQuestion(e.target.value)} />
          </label>
          <button onClick={askChat} disabled={loading}>
            {loading ? "Thinking..." : "Ask"}
          </button>
        </div>
        {chatAnswer ? <div className="answer-box">{chatAnswer}</div> : null}
      </section>
    </>
  );

  return (
    <div className="pro-app">
      <div className="orb orb-a" />
      <div className="orb orb-b" />

      <header className="masthead">
        <div className="masthead-left">
          <p className="eyebrow">Institutional Trading Workspace</p>
          <h1>Vyoma Trade Terminal</h1>
        </div>
        <div className="masthead-right">
          <span className="status-chip">API {health}</span>
          <span className="status-chip">Mode {mode.toUpperCase()}</span>
          <span className="status-chip">Symbol {symbol}</span>
          <button onClick={refreshHealth} type="button">
            Refresh Status
          </button>
        </div>
      </header>

      <section className="command-deck">
        <form className="analysis-form" onSubmit={runAnalysis}>
          <label>
            Symbol
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              <option value="NIFTY">NIFTY</option>
              <option value="BANKNIFTY">BANKNIFTY</option>
              <option value="SENSEX">SENSEX</option>
              <option value="RELIANCE">RELIANCE</option>
              <option value="TCS">TCS</option>
              <option value="HDFCBANK">HDFCBANK</option>
              <option value="ICICIBANK">ICICIBANK</option>
            </select>
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
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="check-inline">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            Alerts
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Analyzing..." : "Run Analysis"}
          </button>
        </form>
        <div className="action-pills">
          <button type="button" onClick={runScanner} disabled={loading}>
            Nifty50 Scan
          </button>
          <button type="button" onClick={syncGrowwPortfolio} disabled={loading}>
            Sync Groww
          </button>
          <button type="button" onClick={() => setView("dashboard")}>
            Open Dashboard
          </button>
        </div>
      </section>

      <section className="market-strip">
        {dashboardKpis.map((kpi) => (
          <article key={kpi.label} className={`kpi-tile ${kpi.tone}`}>
            <p>{kpi.label}</p>
            <strong>{kpi.value}</strong>
          </article>
        ))}
      </section>

      <div className="content-layout">
        <aside className="navigation-rail">
          <nav className="nav-list">
            {VIEW_ITEMS.map((item, idx) => (
              <button
                key={item.key}
                className={`nav-item ${view === item.key ? "current" : ""}`}
                onClick={() => setView(item.key)}
                type="button"
              >
                <em>{String(idx + 1).padStart(2, "0")}</em>
                <strong>{item.label}</strong>
                <span>{item.hint}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className="workspace">
          <header className="workspace-head">
            <div>
              <h2>{VIEW_ITEMS.find((x) => x.key === view)?.label}</h2>
              <p>{VIEW_ITEMS.find((x) => x.key === view)?.hint}</p>
            </div>
            <div className="workspace-head-stats">
              <span>Symbol: {symbol}</span>
              <span>Segment: {segment.replace(/_/g, " ")}</span>
              <span>Timeframe: {timeframe}</span>
            </div>
          </header>

          <section className="workspace-grid">
            {view === "dashboard" ? renderDashboard() : null}
            {view === "scanner" ? renderScanner() : null}
            {view === "options" ? renderOptionsDesk() : null}
            {view === "strategy" ? renderStrategyLab() : null}
            {view === "portfolio" ? renderPortfolio() : null}
            {view === "execution" ? renderExecution() : null}
            {view === "chat" ? renderChat() : null}
          </section>
        </main>
      </div>

      {error ? <aside className="error-toast">{error}</aside> : null}
    </div>
  );
}
