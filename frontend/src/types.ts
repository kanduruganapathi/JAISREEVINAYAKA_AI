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

export type PortfolioResponse = {
  total_value: number;
  invested_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  concentration_risk_pct: number;
  value_at_risk_95: number;
  recommendations: string[];
};
