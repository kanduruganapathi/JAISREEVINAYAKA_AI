export type Bias = "bullish" | "bearish" | "neutral";

export type AnalysisResponse = {
  symbol: string;
  segment: string;
  regime: string;
  score: number;
  consensus_bias: Bias;
  trade_plan: {
    action: "buy" | "sell" | "hold";
    entry: number | null;
    stop_loss: number | null;
    target: number | null;
    rationale: string;
  };
  risk: {
    max_position_size: number;
    stop_loss_pct: number;
    take_profit_pct: number;
    risk_reward_ratio: number;
    warnings: string[];
  };
  indicator_snapshot: {
    ema_20: number;
    ema_50: number;
    rsi_14: number;
    macd: number;
    signal: number;
    histogram: number;
    atr_14: number;
    volatility: number;
  };
  timeframe_biases: Array<{
    timeframe: string;
    bias: Bias;
    confidence: number;
    note: string;
  }>;
  market_structure: {
    trend: string;
    bos: string;
    choch: string;
    support: number[];
    resistance: number[];
    premium_zone: Record<string, number> | null;
    discount_zone: Record<string, number> | null;
    liquidity_sweeps: Array<Record<string, unknown>>;
    fvg_zones: Array<Record<string, unknown>>;
    order_blocks: Array<Record<string, unknown>>;
  } | null;
  strategy_ideas: Array<{
    name: string;
    instrument: string;
    direction: Bias;
    setup: string;
    entry_trigger: string;
    stop_rule: string;
    targets: string[];
    confidence: number;
    timeframe: string;
  }>;
  execution_checklist: string[];
  signals: Array<{
    agent: string;
    bias: Bias;
    confidence: number;
    summary: string;
    details: Record<string, unknown>;
  }>;
  timestamp: string;
};

export type BacktestResponse = {
  symbol: string;
  total_return_pct: number;
  win_rate_pct: number;
  max_drawdown_pct: number;
  sharpe: number;
  equity_curve: Array<{
    ts: string;
    equity: number;
  }>;
  trades: Array<{
    entry_ts: string;
    exit_ts: string;
    side: "long" | "short";
    entry: number;
    exit: number;
    qty: number;
    pnl: number;
    pnl_pct: number;
  }>;
};

export type OrderResponse = {
  status: "accepted" | "rejected" | "simulated";
  order_id: string;
  mode: string;
  message: string;
  broker_payload?: Record<string, unknown>;
};

export type PortfolioResponse = {
  total_value: number;
  invested_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  concentration_risk_pct: number;
  value_at_risk_95: number;
  recommendations: string[];
};

export type GrowwPortfolioSyncResponse = {
  sync: {
    status: string;
    source: string;
    message: string;
    total_positions: number;
  };
  positions: Array<{
    symbol: string;
    qty: number;
    avg_price: number;
    last_price: number;
  }>;
  analysis: PortfolioResponse;
};

export type StockScanResponse = {
  universe: string;
  timeframe: string;
  generated_at: string;
  summary: {
    scanned: number;
    bullish: number;
    bearish: number;
    neutral: number;
    high_confidence: number;
  };
  results: Array<{
    symbol: string;
    rank: number;
    overall_score: number;
    bias: Bias;
    action: "buy" | "sell" | "watch";
    technical: { score: number; signal: Bias; summary: string; meta?: Record<string, string> };
    breakout: { score: number; signal: Bias; summary: string; meta?: Record<string, string> };
    fundamental: { score: number; signal: Bias; summary: string; meta?: Record<string, string> };
    news: { score: number; signal: Bias; summary: string; meta?: Record<string, string> };
    technical_snapshot: Record<string, number>;
    intraday_plan: {
      direction: "long" | "short" | "neutral";
      setup: string;
      entry_zone: string;
      stop_loss: string;
      targets: string[];
      invalidation: string;
      rr_estimate: number;
    };
  }>;
};
