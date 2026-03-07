import { FormEvent, useEffect, useMemo, useState } from "react";

import { api } from "./api/client";
import {
  AnalysisResponse,
  AutoPaperWorkflowResponse,
  BacktestResponse,
  GrowwPortfolioSyncResponse,
  OrderResponse,
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

type StrategyName =
  | "smc_breakout"
  | "ema_cross"
  | "rsi_reversion"
  | "multi_timeframe_breakout"
  | "smc_liquidity_reversal"
  | "fvg_ob_retest"
  | "volume_displacement_breakout"
  | "premium_discount_reversion"
  | "hybrid_confluence_intraday";
type StrategyParamMap = Record<string, number>;

type StrategyTemplate = {
  label: string;
  description: string;
  params: Array<{ key: string; label: string; min: number; max: number; step: number }>;
  defaults: StrategyParamMap;
};

const STRATEGY_TEMPLATES: Record<StrategyName, StrategyTemplate> = {
  smc_breakout: {
    label: "SMC Breakout",
    description: "BOS/CHOCH structure with displacement and RSI filter.",
    params: [
      { key: "bull_rsi_min", label: "Bull RSI Min", min: 20, max: 80, step: 1 },
      { key: "bear_rsi_max", label: "Bear RSI Max", min: 20, max: 80, step: 1 },
      { key: "require_displacement", label: "Require Displacement (1/0)", min: 0, max: 1, step: 1 },
      { key: "min_histogram_strength", label: "Min Histogram", min: 0, max: 2, step: 0.01 },
    ],
    defaults: {
      bull_rsi_min: 48,
      bear_rsi_max: 52,
      require_displacement: 1,
      min_histogram_strength: 0.01,
    },
  },
  ema_cross: {
    label: "EMA Cross",
    description: "Trend-following cross with gap and price confirmation.",
    params: [
      { key: "fast_ema", label: "Fast EMA", min: 5, max: 120, step: 1 },
      { key: "slow_ema", label: "Slow EMA", min: 10, max: 240, step: 1 },
      { key: "confirm_price_above_ema", label: "Price Confirm (1/0)", min: 0, max: 1, step: 1 },
      { key: "trend_gap_bps", label: "Trend Gap (bps)", min: 0, max: 200, step: 1 },
    ],
    defaults: {
      fast_ema: 20,
      slow_ema: 50,
      confirm_price_above_ema: 1,
      trend_gap_bps: 6,
    },
  },
  rsi_reversion: {
    label: "RSI Reversion",
    description: "Mean-reversion entries with neutral zone filter.",
    params: [
      { key: "oversold", label: "Oversold", min: 5, max: 50, step: 1 },
      { key: "overbought", label: "Overbought", min: 50, max: 95, step: 1 },
      { key: "exit_rsi", label: "Exit RSI", min: 20, max: 80, step: 1 },
      { key: "neutral_band", label: "Neutral Band", min: 1, max: 15, step: 0.5 },
    ],
    defaults: {
      oversold: 30,
      overbought: 70,
      exit_rsi: 50,
      neutral_band: 4,
    },
  },
  multi_timeframe_breakout: {
    label: "MTF Breakout",
    description: "Range breakout with configurable lookback and buffer.",
    params: [
      { key: "breakout_lookback", label: "Lookback Candles", min: 10, max: 120, step: 1 },
      { key: "breakout_buffer_bps", label: "Buffer (bps)", min: 0, max: 60, step: 1 },
    ],
    defaults: {
      breakout_lookback: 20,
      breakout_buffer_bps: 5,
    },
  },
  smc_liquidity_reversal: {
    label: "SMC Liquidity Reversal",
    description: "Liquidity sweep + CHOCH reversal + displacement confirmation.",
    params: [
      { key: "require_choch", label: "Require CHOCH (1/0)", min: 0, max: 1, step: 1 },
      { key: "long_rsi_floor", label: "Long RSI Floor", min: 5, max: 65, step: 1 },
      { key: "short_rsi_cap", label: "Short RSI Cap", min: 35, max: 95, step: 1 },
      { key: "min_body_atr_ratio", label: "Min Body/ATR", min: 0, max: 4, step: 0.05 },
    ],
    defaults: {
      require_choch: 1,
      long_rsi_floor: 34,
      short_rsi_cap: 66,
      min_body_atr_ratio: 0.45,
    },
  },
  fvg_ob_retest: {
    label: "FVG + OB Retest",
    description: "Trade only when price retests fresh fair-value-gap or order-block zone.",
    params: [
      { key: "require_displacement", label: "Require Displacement (1/0)", min: 0, max: 1, step: 1 },
      { key: "min_body_atr_ratio", label: "Min Body/ATR", min: 0, max: 4, step: 0.05 },
      { key: "zone_recent_window", label: "Zone Recent Window", min: 8, max: 100, step: 1 },
    ],
    defaults: {
      require_displacement: 1,
      min_body_atr_ratio: 0.35,
      zone_recent_window: 30,
    },
  },
  volume_displacement_breakout: {
    label: "Volume Displacement Breakout",
    description: "Breakout with volume surge, displacement candle and trend alignment.",
    params: [
      { key: "breakout_lookback", label: "Breakout Lookback", min: 10, max: 140, step: 1 },
      { key: "volume_multiplier", label: "Volume Multiplier", min: 0.5, max: 5, step: 0.05 },
      { key: "breakout_buffer_bps", label: "Breakout Buffer (bps)", min: 0, max: 80, step: 1 },
      { key: "min_body_atr_ratio", label: "Min Body/ATR", min: 0, max: 5, step: 0.05 },
    ],
    defaults: {
      breakout_lookback: 24,
      volume_multiplier: 1.35,
      breakout_buffer_bps: 5,
      min_body_atr_ratio: 0.65,
    },
  },
  premium_discount_reversion: {
    label: "Premium/Discount Reversion",
    description: "Mean-reversion from premium-discount zones using SMC filters.",
    params: [
      { key: "long_rsi_max", label: "Long RSI Max", min: 10, max: 65, step: 1 },
      { key: "short_rsi_min", label: "Short RSI Min", min: 35, max: 95, step: 1 },
      { key: "level_threshold", label: "S/R Threshold", min: 0.001, max: 0.03, step: 0.0005 },
      { key: "zone_recent_window", label: "Zone Recent Window", min: 8, max: 100, step: 1 },
    ],
    defaults: {
      long_rsi_max: 45,
      short_rsi_min: 55,
      level_threshold: 0.0035,
      zone_recent_window: 30,
    },
  },
  hybrid_confluence_intraday: {
    label: "Hybrid Confluence Intraday",
    description: "News + fundamental + technical + SMC + price-action unified model.",
    params: [
      { key: "news_score", label: "News Score", min: 0, max: 1, step: 0.01 },
      { key: "fundamental_score", label: "Fundamental Score", min: 0, max: 1, step: 0.01 },
      { key: "long_threshold", label: "Long Threshold", min: 1, max: 10, step: 0.1 },
      { key: "short_threshold", label: "Short Threshold", min: 1, max: 10, step: 0.1 },
    ],
    defaults: {
      news_score: 0.5,
      fundamental_score: 0.5,
      long_threshold: 3.4,
      short_threshold: 3.4,
    },
  },
};

const STRATEGY_ORDER: StrategyName[] = [
  "hybrid_confluence_intraday",
  "smc_liquidity_reversal",
  "fvg_ob_retest",
  "volume_displacement_breakout",
  "premium_discount_reversion",
  "smc_breakout",
  "ema_cross",
  "rsi_reversion",
  "multi_timeframe_breakout",
];

type PaperTradeLog = {
  ts: string;
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  status: string;
  orderId: string;
  message: string;
};

type BacktestQualityCheck = {
  name: string;
  pass: boolean;
  current: string;
  target: string;
};

type BacktestQualitySummary = {
  verdict: "PASS" | "WATCH" | "FAIL";
  grade: "A" | "B" | "C" | "D" | "E";
  checks: BacktestQualityCheck[];
  passCount: number;
  totalChecks: number;
  profitFactor: number | null;
  expectancyPerTrade: number;
};

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

function defaultStrategyParams(rule: StrategyName): StrategyParamMap {
  return { ...STRATEGY_TEMPLATES[rule].defaults };
}

function recommendedStrategyForPick(
  item: StockScanResponse["results"][number]
): StrategyName {
  if (
    item.news.score >= 0.6 &&
    item.fundamental.score >= 0.55 &&
    item.technical.score >= 0.58 &&
    item.breakout.score >= 0.55
  ) {
    return "hybrid_confluence_intraday";
  }
  if (item.breakout.score >= 0.72 && item.technical.score >= 0.6) return "volume_displacement_breakout";
  if (item.technical.score >= 0.62 && item.breakout.score >= 0.55) return "fvg_ob_retest";
  if (item.news.signal !== item.technical.signal && item.technical.signal !== "neutral") return "smc_liquidity_reversal";
  if (item.bias === "neutral") return "rsi_reversion";
  return "smc_breakout";
}

function strategyParamsFromScanItem(
  rule: StrategyName,
  item: StockScanResponse["results"][number]
): StrategyParamMap {
  const params = defaultStrategyParams(rule);
  if (rule === "hybrid_confluence_intraday") {
    params.news_score = Number(item.news.score.toFixed(2));
    params.fundamental_score = Number(item.fundamental.score.toFixed(2));
  }
  return params;
}

function evaluateBacktestQuality(backtest: BacktestResponse): BacktestQualitySummary {
  const totalTrades = backtest.trades.length;
  const grossProfit = backtest.trades
    .filter((trade) => trade.pnl > 0)
    .reduce((sum, trade) => sum + trade.pnl, 0);
  const grossLossAbs = Math.abs(
    backtest.trades
      .filter((trade) => trade.pnl < 0)
      .reduce((sum, trade) => sum + trade.pnl, 0)
  );
  const totalPnl = backtest.trades.reduce((sum, trade) => sum + trade.pnl, 0);
  const expectancyPerTrade = totalTrades > 0 ? totalPnl / totalTrades : 0;
  const profitFactor = grossLossAbs > 0 ? grossProfit / grossLossAbs : grossProfit > 0 ? 99 : null;

  const checks: BacktestQualityCheck[] = [
    {
      name: "Sample Size",
      pass: totalTrades >= 30,
      current: `${totalTrades} trades`,
      target: ">= 30 trades",
    },
    {
      name: "Total Return",
      pass: backtest.total_return_pct >= 3,
      current: `${fmt(backtest.total_return_pct)}%`,
      target: ">= 3.00%",
    },
    {
      name: "Win Rate",
      pass: backtest.win_rate_pct >= 42,
      current: `${fmt(backtest.win_rate_pct)}%`,
      target: ">= 42.00%",
    },
    {
      name: "Sharpe",
      pass: backtest.sharpe >= 0.8,
      current: fmt(backtest.sharpe),
      target: ">= 0.80",
    },
    {
      name: "Max Drawdown",
      pass: backtest.max_drawdown_pct <= 4,
      current: `${fmt(backtest.max_drawdown_pct)}%`,
      target: "<= 4.00%",
    },
  ];

  const passCount = checks.filter((check) => check.pass).length;
  const totalChecks = checks.length;

  let verdict: BacktestQualitySummary["verdict"] = "FAIL";
  if (passCount === totalChecks) {
    verdict = "PASS";
  } else if (passCount >= 3) {
    verdict = "WATCH";
  }

  const grade: BacktestQualitySummary["grade"] =
    passCount === 5 ? "A" : passCount === 4 ? "B" : passCount === 3 ? "C" : passCount === 2 ? "D" : "E";

  return {
    verdict,
    grade,
    checks,
    passCount,
    totalChecks,
    profitFactor,
    expectancyPerTrade,
  };
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

  const [strategy, setStrategy] = useState<StrategyName>("smc_breakout");
  const [strategyParams, setStrategyParams] = useState<StrategyParamMap>(() =>
    defaultStrategyParams("smc_breakout")
  );
  const [backtestTimeframe, setBacktestTimeframe] = useState("15m");
  const [backtestLookback, setBacktestLookback] = useState(380);
  const [capital, setCapital] = useState(100000);
  const [positionsText, setPositionsText] = useState(defaultPositions);
  const [selectedScanSymbol, setSelectedScanSymbol] = useState("");
  const [quickTradeQty, setQuickTradeQty] = useState(25);
  const [scanBacktests, setScanBacktests] = useState<Record<string, BacktestResponse>>({});
  const [paperTradeLogs, setPaperTradeLogs] = useState<PaperTradeLog[]>([]);
  const [scannerTimeframe, setScannerTimeframe] = useState("15m");
  const [scannerTopN, setScannerTopN] = useState(15);
  const [autoMaxPaperTrades, setAutoMaxPaperTrades] = useState(3);
  const [autoMinScannerScore, setAutoMinScannerScore] = useState(0.58);
  const [autoMinWinRate, setAutoMinWinRate] = useState(45);
  const [autoMinReturnPct, setAutoMinReturnPct] = useState(0);
  const [autoMinSharpe, setAutoMinSharpe] = useState(0);
  const [autoWorkflowResult, setAutoWorkflowResult] = useState<AutoPaperWorkflowResponse | null>(null);
  const [riskPerTradePct, setRiskPerTradePct] = useState(1);
  const [dailyLossLimitPct, setDailyLossLimitPct] = useState(2);

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

  const strategyTemplate = STRATEGY_TEMPLATES[strategy];

  const selectedScanItem = useMemo(() => {
    if (!scanner || !selectedScanSymbol) return null;
    return scanner.results.find((x) => x.symbol === selectedScanSymbol) ?? null;
  }, [scanner, selectedScanSymbol]);

  const suggestedQty = useMemo(() => {
    if (analysis?.trade_plan.entry == null || analysis.trade_plan.stop_loss == null) return 0;
    const stopDistance = Math.abs(analysis.trade_plan.entry - analysis.trade_plan.stop_loss);
    if (stopDistance <= 0) return 0;
    const riskCapital = capital * (riskPerTradePct / 100);
    return Math.max(1, Math.floor(riskCapital / stopDistance));
  }, [analysis, capital, riskPerTradePct]);

  const tradeQualification = useMemo(() => {
    if (!analysis) return null;
    const rr = analysis.risk.risk_reward_ratio;
    const alignedTimeframes = analysis.timeframe_biases.filter(
      (tf) => tf.bias === analysis.consensus_bias
    ).length;
    const hasPlanLevels =
      analysis.trade_plan.entry !== null &&
      analysis.trade_plan.stop_loss !== null &&
      analysis.trade_plan.target !== null;
    const newsAligned =
      liveNews.sentiment === "neutral" ||
      (liveNews.sentiment.toLowerCase().includes("positive") && analysis.consensus_bias === "bullish") ||
      (liveNews.sentiment.toLowerCase().includes("negative") && analysis.consensus_bias === "bearish");

    const checks = [
      { name: "System Score", pass: analysis.score >= 0.65, note: `${Math.round(analysis.score * 100)}%` },
      { name: "Risk Reward", pass: rr >= 1.8, note: fmt(rr) },
      {
        name: "Multi-Timeframe Alignment",
        pass: alignedTimeframes >= 3,
        note: `${alignedTimeframes}/${analysis.timeframe_biases.length}`,
      },
      { name: "News Alignment", pass: newsAligned, note: liveNews.sentiment.toUpperCase() },
      { name: "Entry Plan Completeness", pass: hasPlanLevels, note: hasPlanLevels ? "Complete" : "Missing levels" },
    ];

    const passed = checks.filter((x) => x.pass).length;
    const ratio = passed / checks.length;
    const decision = ratio >= 0.8 ? "TRADE READY" : ratio >= 0.6 ? "WATCHLIST" : "AVOID";
    return {
      checks,
      passed,
      total: checks.length,
      ratio,
      decision,
    };
  }, [analysis, liveNews]);

  const backtestQuality = useMemo(() => {
    if (!backtest) return null;
    return evaluateBacktestQuality(backtest);
  }, [backtest]);

  useEffect(() => {
    if (!scanner?.results.length) return;
    if (!selectedScanSymbol || !scanner.results.some((x) => x.symbol === selectedScanSymbol)) {
      setSelectedScanSymbol(scanner.results[0].symbol);
    }
  }, [scanner, selectedScanSymbol]);

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
        timeframe: scannerTimeframe,
        top_n: scannerTopN,
        include_news: true,
        include_fundamental: true,
        include_breakout: true,
        include_technical: true,
      })) as StockScanResponse;
      setScanner(result);
      setAutoWorkflowResult(null);
      setView("scanner");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const setStrategyRule = (nextRule: StrategyName) => {
    setStrategy(nextRule);
    setStrategyParams(defaultStrategyParams(nextRule));
  };

  const updateStrategyParam = (key: string, value: number) => {
    setStrategyParams((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const runBacktest = async (opts?: {
    symbol?: string;
    segment?: string;
    ruleName?: StrategyName;
    params?: StrategyParamMap;
    keepScannerView?: boolean;
  }) => {
    const targetSymbol = opts?.symbol ?? symbol;
    const targetSegment = opts?.segment ?? segment;
    const ruleName = opts?.ruleName ?? strategy;
    let params = { ...(opts?.params ?? strategyParams) };
    if (ruleName === "hybrid_confluence_intraday" && !opts?.params && analysis) {
      const newsSignal = analysis.signals.find((x) => x.agent === "news_analyst");
      const fundamentalSignal = analysis.signals.find((x) => x.agent === "fundamental_analyst");
      params = {
        ...params,
        news_score: Number((newsSignal?.confidence ?? liveNews.score ?? 0.5).toFixed(2)),
        fundamental_score: Number((fundamentalSignal?.confidence ?? 0.5).toFixed(2)),
      };
      setStrategyParams(params);
    }

    setError("");
    setLoading(true);
    try {
      const result = (await api.runBacktest({
        symbol: targetSymbol,
        segment: targetSegment,
        candles: [],
        timeframe: backtestTimeframe,
        lookback_candles: backtestLookback,
        initial_capital: capital,
        commission_per_trade: 20,
        slippage_bps: 5,
        rule: { name: ruleName, params },
      })) as BacktestResponse;
      setBacktest(result);
      setScanBacktests((prev) => ({
        ...prev,
        [targetSymbol]: result,
      }));
      if (!opts?.keepScannerView) {
        setView("strategy");
      }
      return result;
    } catch (err) {
      setError(String(err));
      return null;
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

  const placeOrder = async (opts?: {
    symbol?: string;
    side?: "buy" | "sell";
    mode?: "paper" | "live";
    segment?: "equity" | "index_option" | "stock_option";
    qty?: number;
    keepScannerView?: boolean;
  }) => {
    const targetSymbol = opts?.symbol ?? symbol;
    const targetMode = opts?.mode ?? mode;
    const targetSide = opts?.side ?? (analysis?.trade_plan.action === "sell" ? "sell" : "buy");
    const targetQty = opts?.qty ?? qty;
    const targetSegment =
      opts?.segment ??
      (segment.includes("option")
        ? (segment.includes("stock") ? "stock_option" : "index_option")
        : "equity");

    setError("");
    setLoading(true);
    try {
      const result = (await api.placeOrder({
        symbol: targetSymbol,
        segment: targetSegment,
        side: targetSide,
        qty: targetQty,
        order_type: "market",
        product_type: "intraday",
        mode: targetMode,
      })) as OrderResponse;
      setOrderMsg(`${result.status.toUpperCase()} | ${result.order_id} | ${result.message}`);
      if (targetMode === "paper") {
        setPaperTradeLogs((prev) => [
          {
            ts: new Date().toISOString(),
            symbol: targetSymbol,
            side: targetSide,
            qty: targetQty,
            status: result.status,
            orderId: result.order_id,
            message: result.message,
          },
          ...prev,
        ]);
      }
      if (!opts?.keepScannerView) {
        setView("execution");
      }
      return result;
    } catch (err) {
      setError(String(err));
      return null;
    } finally {
      setLoading(false);
    }
  };

  const runScannerBacktest = async (item: StockScanResponse["results"][number]) => {
    const recommendedRule = recommendedStrategyForPick(item);
    const recommendedParams = strategyParamsFromScanItem(recommendedRule, item);
    setSymbol(item.symbol);
    setSegment("equity");
    setStrategyRule(recommendedRule);
    setStrategyParams(recommendedParams);
    setSelectedScanSymbol(item.symbol);
    await runBacktest({
      symbol: item.symbol,
      segment: "equity",
      ruleName: recommendedRule,
      params: recommendedParams,
      keepScannerView: true,
    });
  };

  const runScannerPaperTrade = async (
    item: StockScanResponse["results"][number],
    forcedSide?: "buy" | "sell"
  ) => {
    if (!forcedSide && item.action === "watch" && item.bias === "neutral") {
      setError(`No directional edge for ${item.symbol}. Run fresh scan or wait for breakout confirmation.`);
      return;
    }
    const side =
      forcedSide ??
      (item.action === "buy"
        ? "buy"
        : item.action === "sell"
          ? "sell"
          : item.bias === "bullish"
            ? "buy"
            : "sell");
    setSymbol(item.symbol);
    setSegment("equity");
    setMode("paper");
    setQty(quickTradeQty);
    setSelectedScanSymbol(item.symbol);
    await placeOrder({
      symbol: item.symbol,
      side,
      qty: quickTradeQty,
      mode: "paper",
      segment: "equity",
      keepScannerView: true,
    });
  };

  const runAutoPaperWorkflow = async () => {
    setError("");
    setLoading(true);
    try {
      const result = (await api.runAutoPaperWorkflow({
        universe: "nifty50",
        symbols: [],
        timeframe: scannerTimeframe,
        top_n: scannerTopN,
        include_news: true,
        include_fundamental: true,
        include_breakout: true,
        include_technical: true,
        backtest_lookback_candles: backtestLookback,
        initial_capital: capital,
        risk_per_trade_pct: riskPerTradePct,
        max_paper_trades: autoMaxPaperTrades,
        min_scanner_score: autoMinScannerScore,
        min_backtest_win_rate: autoMinWinRate,
        min_backtest_return_pct: autoMinReturnPct,
        min_backtest_sharpe: autoMinSharpe,
        min_backtest_trades: 4,
        require_directional_action: true,
      })) as AutoPaperWorkflowResponse;
      setAutoWorkflowResult(result);

      const btMap: Record<string, BacktestResponse> = {};
      result.results.forEach((row) => {
        btMap[row.symbol] = {
          symbol: row.symbol,
          total_return_pct: row.backtest.total_return_pct,
          win_rate_pct: row.backtest.win_rate_pct,
          max_drawdown_pct: row.backtest.max_drawdown_pct,
          sharpe: row.backtest.sharpe,
          trades: [],
          equity_curve: [],
        };
      });
      setScanBacktests((prev) => ({ ...prev, ...btMap }));

      const newPaperLogs: PaperTradeLog[] = result.results
        .filter((x) => !!x.order)
        .map((x) => ({
          ts: result.generated_at,
          symbol: x.symbol,
          side: x.risk_plan?.side ?? "buy",
          qty: x.risk_plan?.qty ?? 0,
          status: x.order?.status ?? "unknown",
          orderId: x.order?.order_id ?? "-",
          message: x.order?.message ?? "",
        }));
      if (newPaperLogs.length) {
        setPaperTradeLogs((prev) => [...newPaperLogs, ...prev]);
      }
      setView("scanner");
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

        <section className="panel panel-wide">
          <div className="panel-topline">
            <h3>Trade Qualification Engine</h3>
            <span
              className={`grade-chip ${
                tradeQualification?.decision === "TRADE READY"
                  ? "bias-bull"
                  : tradeQualification?.decision === "WATCHLIST"
                    ? "bias-neutral"
                    : "bias-bear"
              }`}
            >
              {tradeQualification?.decision ?? "NO SIGNAL"}
            </span>
          </div>
          <div className="quality-grid">
            {tradeQualification?.checks.map((check) => (
              <article key={check.name} className={`quality-item ${check.pass ? "pass" : "fail"}`}>
                <strong>{check.name}</strong>
                <span>{check.note}</span>
              </article>
            ))}
          </div>
          <div className="headline-grid">
            <article>
              <label>Checks Passed</label>
              <p className="big">
                {tradeQualification?.passed}/{tradeQualification?.total}
              </p>
            </article>
            <article>
              <label>Risk Per Trade</label>
              <p className="big">{fmt(riskPerTradePct)}%</p>
            </article>
            <article>
              <label>Daily Loss Limit</label>
              <p className="big">{fmt(dailyLossLimitPct)}%</p>
            </article>
            <article>
              <label>Suggested Qty</label>
              <p className="big">{suggestedQty || "-"}</p>
            </article>
          </div>
          <div className="controls-grid">
            <label>
              Risk Per Trade (%)
              <input
                type="number"
                min={0.25}
                max={3}
                step={0.25}
                value={riskPerTradePct}
                onChange={(e) => setRiskPerTradePct(Math.max(0.25, Math.min(3, Number(e.target.value || 1))))}
              />
            </label>
            <label>
              Daily Loss Limit (%)
              <input
                type="number"
                min={1}
                max={8}
                step={0.5}
                value={dailyLossLimitPct}
                onChange={(e) => setDailyLossLimitPct(Math.max(1, Math.min(8, Number(e.target.value || 2))))}
              />
            </label>
            <button
              type="button"
              onClick={() => setQty(suggestedQty || qty)}
              disabled={!suggestedQty}
            >
              Use Suggested Qty in Execution
            </button>
          </div>
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
    const selectedBacktest = selectedScanSymbol ? scanBacktests[selectedScanSymbol] : null;

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
          </div>
          <div className="controls-grid">
            <label>
              Scanner Timeframe
              <select value={scannerTimeframe} onChange={(e) => setScannerTimeframe(e.target.value)}>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="1d">1d</option>
              </select>
            </label>
            <label>
              Top Opportunities
              <input
                type="number"
                min={5}
                max={50}
                value={scannerTopN}
                onChange={(e) => setScannerTopN(Math.max(5, Math.min(50, Number(e.target.value || 15))))}
              />
            </label>
            <button onClick={runScanner} disabled={loading}>
              {loading ? "Scanning..." : "Run Nifty 50 Scan"}
            </button>
          </div>
        </section>

        <section className="panel panel-wide">
          <div className="row-head">
            <div>
              <h3>Auto Strategy, Backtest and Paper Workflow</h3>
              <p>Automatically picks strategies from scan factors, validates with backtest, and places paper trades.</p>
            </div>
            <button onClick={runAutoPaperWorkflow} disabled={loading}>
              {loading ? "Running Workflow..." : "Run Auto Workflow"}
            </button>
          </div>
          <div className="controls-grid">
            <label>
              Max Paper Trades
              <input
                type="number"
                min={1}
                max={20}
                value={autoMaxPaperTrades}
                onChange={(e) => setAutoMaxPaperTrades(Math.max(1, Math.min(20, Number(e.target.value || 3))))}
              />
            </label>
            <label>
              Min Scanner Score
              <input
                type="number"
                min={0.4}
                max={0.95}
                step={0.01}
                value={autoMinScannerScore}
                onChange={(e) => setAutoMinScannerScore(Math.max(0.4, Math.min(0.95, Number(e.target.value || 0.58))))}
              />
            </label>
            <label>
              Min Win Rate (%)
              <input
                type="number"
                min={20}
                max={80}
                step={1}
                value={autoMinWinRate}
                onChange={(e) => setAutoMinWinRate(Math.max(20, Math.min(80, Number(e.target.value || 45))))}
              />
            </label>
            <label>
              Min Backtest Return (%)
              <input
                type="number"
                min={-10}
                max={50}
                step={0.5}
                value={autoMinReturnPct}
                onChange={(e) => setAutoMinReturnPct(Math.max(-10, Math.min(50, Number(e.target.value || 0))))}
              />
            </label>
            <label>
              Min Sharpe
              <input
                type="number"
                min={-1}
                max={5}
                step={0.1}
                value={autoMinSharpe}
                onChange={(e) => setAutoMinSharpe(Math.max(-1, Math.min(5, Number(e.target.value || 0))))}
              />
            </label>
            <label>
              Risk Per Trade (%)
              <input
                type="number"
                min={0.25}
                max={3}
                step={0.25}
                value={riskPerTradePct}
                onChange={(e) => setRiskPerTradePct(Math.max(0.25, Math.min(3, Number(e.target.value || 1))))}
              />
            </label>
          </div>
          {autoWorkflowResult ? (
            <>
              <div className="headline-grid">
                <article>
                  <label>Scanned</label>
                  <p className="big">{autoWorkflowResult.summary.scanned}</p>
                </article>
                <article>
                  <label>Backtested</label>
                  <p className="big">{autoWorkflowResult.summary.selected_for_backtest}</p>
                </article>
                <article className="bias-bull">
                  <label>Qualified</label>
                  <p className="big">{autoWorkflowResult.summary.qualified_for_paper}</p>
                </article>
                <article className="bias-bull">
                  <label>Paper Orders</label>
                  <p className="big">{autoWorkflowResult.summary.paper_orders}</p>
                </article>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Strategy</th>
                      <th>Return%</th>
                      <th>Win%</th>
                      <th>Sharpe</th>
                      <th>Gate</th>
                      <th>Reason</th>
                      <th>Order</th>
                    </tr>
                  </thead>
                  <tbody>
                    {autoWorkflowResult.results.map((row) => (
                      <tr key={`${row.symbol}-${row.rank}`}>
                        <td>{row.symbol}</td>
                        <td>{row.chosen_strategy}</td>
                        <td>{fmt(row.backtest.total_return_pct)}%</td>
                        <td>{fmt(row.backtest.win_rate_pct)}%</td>
                        <td>{fmt(row.backtest.sharpe)}</td>
                        <td>{row.gate.passed ? "PASS" : "FAIL"}</td>
                        <td>{row.gate.reasons[0] ?? "Qualified"}</td>
                        <td>{row.order ? `${row.order.status.toUpperCase()} ${row.order.order_id}` : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="muted">Run auto workflow to generate strategy decisions, backtest quality and paper orders.</p>
          )}
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
              <h3>Scan to Strategy and Paper Trade</h3>
              <p className="muted">
                Pick a scanned stock, tune rule parameters, run backtest, then place paper trade instantly.
              </p>
              <div className="controls-grid strategy-builder-grid">
                <label>
                  Selected Scan Pick
                  <select value={selectedScanSymbol} onChange={(e) => setSelectedScanSymbol(e.target.value)}>
                    {scanner.results.map((item) => (
                      <option key={item.symbol} value={item.symbol}>
                        #{item.rank} {item.symbol} ({Math.round(item.overall_score * 100)}%)
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Strategy Rule
                  <select value={strategy} onChange={(e) => setStrategyRule(e.target.value as StrategyName)}>
                    {STRATEGY_ORDER.map((ruleName) => (
                      <option key={ruleName} value={ruleName}>
                        {STRATEGY_TEMPLATES[ruleName].label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Backtest Timeframe
                  <select value={backtestTimeframe} onChange={(e) => setBacktestTimeframe(e.target.value)}>
                    <option value="5m">5m</option>
                    <option value="15m">15m</option>
                    <option value="1h">1h</option>
                    <option value="1d">1d</option>
                  </select>
                </label>
                <label>
                  Lookback Candles
                  <input
                    type="number"
                    min={120}
                    max={2000}
                    value={backtestLookback}
                    onChange={(e) => setBacktestLookback(Number(e.target.value || 380))}
                  />
                </label>
                <label>
                  Initial Capital
                  <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value || 0))} />
                </label>
                <label>
                  Paper Qty
                  <input
                    type="number"
                    min={1}
                    value={quickTradeQty}
                    onChange={(e) => setQuickTradeQty(Math.max(1, Number(e.target.value || 1)))}
                  />
                </label>
              </div>

              <p className="muted">{strategyTemplate.description}</p>
              <div className="param-grid">
                {strategyTemplate.params.map((param) => (
                  <label key={param.key}>
                    {param.label}
                    <input
                      type="number"
                      min={param.min}
                      max={param.max}
                      step={param.step}
                      value={strategyParams[param.key] ?? strategyTemplate.defaults[param.key] ?? 0}
                      onChange={(e) => updateStrategyParam(param.key, Number(e.target.value || 0))}
                    />
                  </label>
                ))}
              </div>

              <div className="quick-actions">
                <button
                  onClick={() =>
                    selectedScanSymbol
                      ? runBacktest({
                          symbol: selectedScanSymbol,
                          segment: "equity",
                          keepScannerView: true,
                        })
                      : null
                  }
                  disabled={loading || !selectedScanSymbol}
                >
                  {loading ? "Running..." : "Backtest Selected Pick"}
                </button>
                <button
                  onClick={() => (selectedScanItem ? runScannerPaperTrade(selectedScanItem, "buy") : null)}
                  disabled={loading || !selectedScanItem}
                >
                  Paper Buy
                </button>
                <button
                  onClick={() => (selectedScanItem ? runScannerPaperTrade(selectedScanItem, "sell") : null)}
                  disabled={loading || !selectedScanItem}
                >
                  Paper Sell
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (!selectedScanSymbol) return;
                    setSymbol(selectedScanSymbol);
                    setSegment("equity");
                    setView("strategy");
                  }}
                  disabled={!selectedScanSymbol}
                >
                  Open Strategy Lab
                </button>
              </div>

              {selectedBacktest ? (
                <div className="kv-grid">
                  <div>
                    <span>Backtest Symbol</span>
                    <strong>{selectedScanSymbol}</strong>
                  </div>
                  <div>
                    <span>Total Return</span>
                    <strong>{fmt(selectedBacktest.total_return_pct)}%</strong>
                  </div>
                  <div>
                    <span>Win Rate</span>
                    <strong>{fmt(selectedBacktest.win_rate_pct)}%</strong>
                  </div>
                  <div>
                    <span>Max Drawdown</span>
                    <strong>{fmt(selectedBacktest.max_drawdown_pct)}%</strong>
                  </div>
                  <div>
                    <span>Sharpe</span>
                    <strong>{fmt(selectedBacktest.sharpe)}</strong>
                  </div>
                  <div>
                    <span>Trades</span>
                    <strong>{selectedBacktest.trades.length}</strong>
                  </div>
                </div>
              ) : (
                <p className="muted">No backtest for selected pick yet. Run backtest to evaluate before paper execution.</p>
              )}
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
                    {scanBacktests[item.symbol] ? (
                      <p className="muted">
                        BT: {fmt(scanBacktests[item.symbol].total_return_pct)}% return •{" "}
                        {fmt(scanBacktests[item.symbol].win_rate_pct)}% win rate
                      </p>
                    ) : null}
                    <div className="card-actions">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedScanSymbol(item.symbol);
                          setSymbol(item.symbol);
                          setSegment("equity");
                          const ruleName = recommendedStrategyForPick(item);
                          setStrategyRule(ruleName);
                          setStrategyParams(strategyParamsFromScanItem(ruleName, item));
                        }}
                      >
                        Build
                      </button>
                      <button type="button" onClick={() => runScannerBacktest(item)} disabled={loading}>
                        Backtest
                      </button>
                      <button type="button" onClick={() => runScannerPaperTrade(item)} disabled={loading}>
                        Paper Trade
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            {paperTradeLogs.length ? (
              <section className="panel panel-wide">
                <h3>Paper Trading Blotter</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Symbol</th>
                        <th>Side</th>
                        <th>Qty</th>
                        <th>Status</th>
                        <th>Order ID</th>
                        <th>Message</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paperTradeLogs.slice(0, 20).map((row) => (
                        <tr key={`${row.ts}-${row.orderId}`}>
                          <td>{new Date(row.ts).toLocaleTimeString()}</td>
                          <td>{row.symbol}</td>
                          <td>{row.side.toUpperCase()}</td>
                          <td>{row.qty}</td>
                          <td>{row.status.toUpperCase()}</td>
                          <td>{row.orderId}</td>
                          <td>{row.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}

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
                      <th>Workflow</th>
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
                        <td>
                          <button
                            type="button"
                            className="table-btn"
                            onClick={() => {
                              setSelectedScanSymbol(item.symbol);
                              setSymbol(item.symbol);
                              setSegment("equity");
                            }}
                          >
                            Select
                          </button>
                        </td>
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
          <p className="muted">Build and validate strategy settings before moving to paper or live execution.</p>
          <div className="controls-grid">
            <label>
              Rule
              <select value={strategy} onChange={(e) => setStrategyRule(e.target.value as StrategyName)}>
                {STRATEGY_ORDER.map((ruleName) => (
                  <option key={ruleName} value={ruleName}>
                    {STRATEGY_TEMPLATES[ruleName].label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Backtest Timeframe
              <select value={backtestTimeframe} onChange={(e) => setBacktestTimeframe(e.target.value)}>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="1d">1d</option>
              </select>
            </label>
            <label>
              Lookback Candles
              <input
                type="number"
                min={120}
                max={2000}
                value={backtestLookback}
                onChange={(e) => setBacktestLookback(Number(e.target.value || 380))}
              />
            </label>
            <label>
              Initial Capital
              <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value || 0))} />
            </label>
            <button onClick={() => runBacktest()} disabled={loading}>
              {loading ? "Running..." : "Run Backtest"}
            </button>
          </div>

          <p className="muted">{strategyTemplate.description}</p>
          <div className="param-grid">
            {strategyTemplate.params.map((param) => (
              <label key={param.key}>
                {param.label}
                <input
                  type="number"
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  value={strategyParams[param.key] ?? strategyTemplate.defaults[param.key] ?? 0}
                  onChange={(e) => updateStrategyParam(param.key, Number(e.target.value || 0))}
                />
              </label>
            ))}
          </div>
        </section>

        {backtest && (
          <section className="panel panel-wide">
            <div className="panel-topline">
              <h3>Backtest Result</h3>
              <span
                className={`grade-chip strategy-grade ${
                  backtestQuality?.verdict === "PASS"
                    ? "bias-bull"
                    : backtestQuality?.verdict === "WATCH"
                      ? "bias-neutral"
                      : "bias-bear"
                }`}
              >
                {backtestQuality ? `Quality ${backtestQuality.verdict} • Grade ${backtestQuality.grade}` : "-"}
              </span>
            </div>
            <p className="muted">
              Gate: trades &gt;= 30, return &gt;= 3%, win rate &gt;= 42%, sharpe &gt;= 0.8, max drawdown &lt;= 4%.
            </p>
            <div className="quality-grid">
              {backtestQuality?.checks.map((check) => (
                <article key={check.name} className={`quality-item ${check.pass ? "pass" : "fail"}`}>
                  <strong>{check.name}</strong>
                  <span>{check.current}</span>
                  <span className="quality-target">Target: {check.target}</span>
                </article>
              ))}
            </div>
            <div className="headline-grid">
              <article>
                <label>Checks Passed</label>
                <p className="big">
                  {backtestQuality?.passCount}/{backtestQuality?.totalChecks}
                </p>
              </article>
              <article>
                <label>Quality Verdict</label>
                <p className="big">{backtestQuality?.verdict ?? "-"}</p>
              </article>
              <article>
                <label>Profit Factor</label>
                <p className="big">{backtestQuality?.profitFactor == null ? "-" : fmt(backtestQuality.profitFactor)}</p>
              </article>
              <article>
                <label>Expectancy / Trade</label>
                <p className="big">{backtestQuality ? fmt(backtestQuality.expectancyPerTrade) : "-"}</p>
              </article>
            </div>
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
              <div>
                <span>Trades</span>
                <strong>{backtest.trades.length}</strong>
              </div>
              <div>
                <span>Final Equity</span>
                <strong>{fmt(backtest.equity_curve[backtest.equity_curve.length - 1]?.equity ?? capital)}</strong>
              </div>
            </div>
            {backtestQuality && backtestQuality.verdict !== "PASS" ? (
              <div className="warn-box">
                <p><b>Not ready for paper or live deployment yet.</b></p>
                <ul className="checklist">
                  {backtestQuality.checks
                    .filter((check) => !check.pass)
                    .map((check) => (
                      <li key={check.name}>
                        {check.name}: {check.current} (target {check.target})
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}
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
        <p className="muted">
          Suggested quantity from risk model: {suggestedQty || "-"} (risk {fmt(riskPerTradePct)}% per trade, daily stop {fmt(dailyLossLimitPct)}%).
        </p>
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
          <button type="button" onClick={() => setQty(suggestedQty || qty)} disabled={!suggestedQty}>
            Apply Suggested Qty
          </button>
          <button onClick={() => placeOrder()} disabled={loading}>
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
          <p className="eyebrow">AI-Powered Trading Workspace</p>
          <h1>AI TRADE</h1>
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
